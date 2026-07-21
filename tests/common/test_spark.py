"""Tests for the Spark session factory.

Small file, one important job: pin the session timezone.
"""

from __future__ import annotations

from dataflow.common.spark import SESSION_TIMEZONE


def test_session_timezone_is_utc(spark):
    """Ingestion must be reproducible on any machine.

    The Stack Exchange dump stores naive timestamps that are UTC. Spark's
    default session timezone is the host machine's, so without this pin the
    same Posts.xml yields different instants depending on who runs it — a
    3-hour shift on the machine this was written on.
    """
    assert spark.conf.get("spark.sql.session.timeZone") == "UTC"
    assert SESSION_TIMEZONE == "UTC"


def test_delta_extensions_are_configured(spark):
    """Without these, writes fall back to Parquet and lose Delta semantics."""
    assert "DeltaSparkSessionExtension" in spark.conf.get("spark.sql.extensions")


def test_get_spark_reuses_an_existing_session(spark):
    """Never build a second session — on Databricks the platform owns it."""
    from dataflow.common.spark import get_spark

    assert get_spark(app_name="should-be-ignored") is spark
