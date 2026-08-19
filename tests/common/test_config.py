"""Tests for config loading.

No Spark here — these are fast, plain-Python tests. They exist because the old
pipeline.yaml drifted into describing a file that did not exist, in a mode the
code did not implement, and nothing noticed. Config that is read by tests
cannot drift silently.
"""

from __future__ import annotations

import pytest

from dataflow.common.config import (
    _search_upwards,
    config_path,
    job_config,
    load_config,
    project_root,
    resolve_path,
    spark_config,
)

SAMPLE = """
spark:
  app_name: test-app
  warehouse_dir: /tmp/test-warehouse

bronze:
  posts:
    source_path: tests/fixtures/posts_sample.xml
    table: bronze_test.posts
    write_mode: overwrite
"""


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "pipeline.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_load_config_parses_yaml(config_file):
    assert load_config(config_file)["spark"]["app_name"] == "test-app"


def test_job_config_returns_the_named_block(config_file):
    cfg = job_config("bronze", "posts", config_file)

    assert cfg["table"] == "bronze_test.posts"
    assert cfg["write_mode"] == "overwrite"


def test_job_config_raises_a_useful_error_for_unknown_jobs(config_file):
    """A typo'd job name must fail loudly, naming what was missing."""
    with pytest.raises(KeyError, match="silver.posts"):
        job_config("silver", "posts", config_file)


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_spark_config_defaults_to_empty(tmp_path):
    """A config with no spark block is valid — callers fall back to defaults."""
    path = tmp_path / "pipeline.yaml"
    path.write_text("bronze:\n  posts:\n    table: t\n", encoding="utf-8")

    assert spark_config(path) == {}


def test_env_var_overrides_config_location(tmp_path, monkeypatch):
    """DATAFLOW_CONFIG is how tests and CI point at a different config."""
    custom = tmp_path / "custom.yaml"
    custom.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("DATAFLOW_CONFIG", str(custom))

    assert config_path() == custom
    assert load_config()["spark"]["app_name"] == "test-app"


def test_search_upwards_finds_config_from_a_nested_directory(tmp_path):
    """Resolution must not depend on how deep the caller happens to be."""
    root = tmp_path / "project"
    (root / "configs").mkdir(parents=True)
    expected = root / "configs" / "pipeline.yaml"
    expected.write_text("bronze:\n  posts:\n    table: t\n", encoding="utf-8")

    nested = root / "src" / "dataflow" / "common"
    nested.mkdir(parents=True)

    assert _search_upwards(nested) == expected


def test_search_upwards_returns_none_when_there_is_no_config(tmp_path):
    assert _search_upwards(tmp_path) is None


def test_config_path_resolves_with_no_env_var_set(monkeypatch):
    """The default path must work in a plain checkout, without configuration.

    Previously this was a fixed parents[3] hop from __file__, which only held
    for an editable install; a non-editable install resolved to somewhere
    inside site-packages.
    """
    monkeypatch.delenv("DATAFLOW_CONFIG", raising=False)

    resolved = config_path()

    assert resolved.is_file()
    assert resolved.name == "pipeline.yaml"


def test_real_config_is_valid_and_complete():
    """The committed configs/pipeline.yaml must actually work.

    This is the test that would have caught the old CSV-that-did-not-exist
    config: it asserts the real file parses and declares what the job reads.
    """
    cfg = job_config("bronze", "posts")

    assert cfg["source_path"].endswith(".xml")
    assert cfg["table"] == "bronze.posts"
    assert cfg["write_mode"] in {"overwrite", "append"}


def test_real_config_declares_the_users_job():
    """Same guarantee as posts: the committed config must match the code.

    `source_path` is the one that bites — the old config pointed at a CSV that
    never existed. `row_tag` is the option that actually selects rows; get it
    wrong and the job writes zero rows and reports success.
    """
    cfg = job_config("bronze", "users")

    assert cfg["source_path"].endswith("Users.xml")
    assert cfg["row_tag"] == "row"
    assert cfg["table"] == "bronze.users"
    assert cfg["write_mode"] in {"overwrite", "append"}


# ---------------------------------------------------------------------------
# Path resolution — the reason jobs work outside the repo root
# ---------------------------------------------------------------------------


def test_project_root_is_the_config_files_grandparent(config_file):
    """configs/pipeline.yaml sits one level below the root."""
    assert project_root(config_file) == config_file.parent.parent


def test_resolve_path_anchors_relative_paths_to_the_project_root(config_file):
    resolved = resolve_path("data/Posts.xml", config_file)

    assert resolved == str(config_file.parent.parent / "data" / "Posts.xml")


def test_resolve_path_leaves_absolute_paths_alone(config_file):
    """The escape hatch for data that lives outside the repo."""
    assert resolve_path("/mnt/dumps/Posts.xml", config_file) == "/mnt/dumps/Posts.xml"


def test_resolve_path_does_not_depend_on_the_working_directory(config_file, tmp_path, monkeypatch):
    """The whole point: same answer from anywhere.

    Airflow runs tasks from its own directory, and Cosmos runs dbt from a
    temporary one. A path resolved against cwd would work from the CLI and
    fail there — the worst kind of bug, because the CLI keeps passing.
    """
    from_root = resolve_path("data/Posts.xml", config_file)

    elsewhere = tmp_path / "somewhere" / "else"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)

    assert resolve_path("data/Posts.xml", config_file) == from_root
