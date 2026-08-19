"""Shared pytest fixtures.

The Spark session is session-scoped on purpose: starting one costs several
seconds, and creating it per-test would make the suite too slow to run often.
A suite nobody runs is worth nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dataflow.common.spark import get_spark

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def spark(tmp_path_factory: pytest.TempPathFactory):
    """A local Spark session with Delta enabled, writing to a temp warehouse.

    The warehouse lives in a temp directory so tests never touch (or dirty)
    the real ./spark-warehouse.
    """
    warehouse = tmp_path_factory.mktemp("warehouse")
    session = get_spark(app_name="dataflow-tests", warehouse_dir=str(warehouse))
    session.sparkContext.setLogLevel("ERROR")

    yield session

    session.stop()


@pytest.fixture(scope="session")
def posts_xml() -> str:
    """Path to a 5-row sample of the real Posts.xml.

    Real rows, not synthetic ones — they carry the awkward parts (HTML-escaped
    bodies, pipe-delimited tags, answers with no title) that hand-written
    fixtures tend to leave out.
    """
    return str(FIXTURES_DIR / "posts_sample.xml")


@pytest.fixture(scope="session")
def users_xml() -> str:
    """Path to a 5-row sample of the real Users.xml.

    Chosen, not random: the Community pseudo-user (Id=-1), a user with every
    optional field filled, one with none of them, and two where an optional
    field is present but empty. Those distinctions are what bronze has to
    preserve, and synthetic rows would not have them.
    """
    return str(FIXTURES_DIR / "users_sample.xml")
