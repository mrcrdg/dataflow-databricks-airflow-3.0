"""Checks that the dashboard generator still produces a working page.

ADR 0002: an artifact must be exercised by something automated, or be deleted.
`viz/build_dashboard.py` writes a file nobody reviews line by line, from queries
that would keep working if a column quietly changed meaning — so this is what
exercises it.

What is asserted is that the page is **structurally sound**: a real document,
self-contained, with every colour token defined outside a theme block. What is
not asserted is the numbers: they come from whichever database is passed in.
The fixture below is deliberately tiny and its values are made up.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "viz" / "build_dashboard.py"


def _load_generator():
    """Import the script by path — it is a tool, not part of the package."""
    spec = importlib.util.spec_from_file_location("build_dashboard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def page(tmp_path_factory) -> str:
    """Build the page from a five-row stand-in for the gold tables."""
    tmp = tmp_path_factory.mktemp("dashboard")
    db = tmp / "fixture.duckdb"

    con = duckdb.connect(str(db))
    con.execute("""
        create table marts_posts_users as
        select * from (values
            (1, 'Question', 3,  12, 2, '2019-04-01'::timestamp, 101, 'ada',   900, 'resolved'),
            (2, 'Answer',   7,  40, 1, '2020-07-15'::timestamp, 102, 'grace', 700, 'resolved'),
            (3, 'Question', 0,   0, 0, '2020-09-30'::timestamp, 103, 'alan',  500, 'anonymous'),
            (4, 'Answer',  -2,   5, 0, '2021-01-05'::timestamp, 101, 'ada',   900, 'resolved'),
            (5, 'Question',  6, 88, 4, '2021-11-20'::timestamp, 104, 'edsger', 50, 'unresolved')
        ) as t(post_id, post_type, score, view_count, answer_count,
               post_creation_date, owner_user_id, display_name, reputation,
               author_status)
    """)
    con.execute("""
        create table marts_top_tags as
        select * from (values
            ('search', 4), ('logic', 3), ('agents', 2)
        ) as t(tag, post_count)
    """)
    con.close()

    out = tmp / "dashboard.html"
    _load_generator().build(str(db), str(out))
    return out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# It has to open as a document from disk
# ---------------------------------------------------------------------------


def test_the_page_is_a_standalone_document(page):
    """Without a doctype it renders in quirks mode; without a charset the
    punctuation decodes as mojibake. Both matter — this file is opened from
    the filesystem, not served."""
    head = page[:300].lower()

    assert head.startswith("<!doctype html>")
    assert 'charset="utf-8"' in head
    assert page.rstrip().endswith("</html>")


def test_the_page_needs_no_local_assets(page):
    """No build step and no asset folder, so moving the file cannot break it.
    Google Fonts is the one remote host, and it degrades to the fallback stack."""
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', page)
    non_fonts = [u for u in external if "fonts.g" not in u]

    assert non_fonts == [], f"page depends on external assets: {non_fonts}"


# ---------------------------------------------------------------------------
# The theme bug this catches is invisible until someone with the other
# setting opens it
# ---------------------------------------------------------------------------


def test_every_colour_token_is_defined_for_the_default_theme(page):
    """A token defined only inside a dark block leaves the un-stamped viewer —
    the default — rendering one theme's text on the other theme's ground."""
    base = page.split("@media (prefers-color-scheme: dark)", 1)[0]
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", page))
    defined = set(re.findall(r"(--[a-z0-9-]+):", base))

    assert used <= defined, f"tokens used but never defined in :root: {sorted(used - defined)}"


def test_the_dark_theme_wins_under_both_selectors(page):
    """The viewer has three states, not two: an explicit stamp either way, and
    the OS setting with no stamp at all."""
    assert ':root:not([data-theme="light"])' in page
    assert ':root[data-theme="dark"]' in page


# ---------------------------------------------------------------------------
# The queries have to have actually run
# ---------------------------------------------------------------------------


def test_the_fixture_numbers_reach_the_page(page):
    """Five posts, three questions, two answers, four distinct authors."""
    assert ">5<" in page or ">5 " in page  # total posts, in a KPI tile
    assert "search" in page and "logic" in page and "agents" in page
    assert "edsger" in page  # the author table ran


def test_a_score_band_with_no_posts_is_not_an_error(page):
    """Sparse data is normal — the fixture has nothing scoring 20 or more. That
    used to raise KeyError, which made the generator unusable against anything
    but the full dump."""
    assert "20+" in page  # the empty band is still drawn, at zero


def test_an_empty_gold_table_fails_loudly(tmp_path):
    """A dashboard built from nothing must not render as a page of zeroes.

    This is the failure this repo keeps meeting: the job succeeds, the output
    looks plausible, and nobody notices it is empty.
    """
    db = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db))
    con.execute("""
        create table marts_posts_users (
            post_id bigint, post_type varchar, score bigint, view_count bigint,
            answer_count bigint, post_creation_date timestamp,
            owner_user_id bigint, display_name varchar, reputation bigint,
            author_status varchar
        )
    """)
    con.execute("create table marts_top_tags (tag varchar, post_count bigint)")
    con.close()

    with pytest.raises(ValueError, match="empty"):
        _load_generator().build(str(db), str(tmp_path / "out.html"))

    assert not (tmp_path / "out.html").exists(), "a failed build must not leave a page behind"
