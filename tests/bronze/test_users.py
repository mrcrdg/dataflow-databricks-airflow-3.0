"""Tests for bronze users ingestion.

Same split as `test_posts.py`:

1. Pure transformation tests — no I/O, fast, the bulk of the value.
2. Ingestion tests — read the fixture file, exercise the reader and writer.

The fixture is five real rows chosen for their awkwardness: a negative id (the
Community pseudo-user), a user with every optional field populated, one with
none of them, and users where an optional field is present but empty. Those are
the cases silver has to distinguish, so bronze has to preserve them.
"""

from __future__ import annotations

from pyspark.sql.functions import date_format
from pyspark.sql.types import LongType, StringType, TimestampType

from dataflow.bronze.users import (
    USERS_SCHEMA,
    clean_columns,
    load_raw_users,
    run,
)

# ---------------------------------------------------------------------------
# Schema — the data contract for the bronze layer
# ---------------------------------------------------------------------------


def test_schema_declares_all_source_attributes():
    """The Stack Exchange Users dump has 12 attributes; all must be declared.

    Guards against a field being dropped during a refactor, which would
    silently discard a column rather than fail loudly.
    """
    assert len(USERS_SCHEMA.fields) == 12


def test_schema_field_names_match_xml_attribute_form():
    """Every declared field carries the leading underscore the XML reader adds.

    Spark's XML reader prefixes attributes with '_'. If a field here were
    written without it, that column would silently read as all-null.
    """
    assert all(f.name.startswith("_") for f in USERS_SCHEMA.fields)


def test_schema_types_are_explicit_not_inferred():
    """Key columns must keep their declared types.

    `_Id` in particular: it is the join key to `Posts.OwnerUserId`, which is
    Long. If it degraded to String the join would silently match nothing.
    """
    types = {f.name: type(f.dataType) for f in USERS_SCHEMA.fields}

    assert types["_Id"] is LongType
    assert types["_Reputation"] is LongType
    assert types["_CreationDate"] is TimestampType
    assert types["_DisplayName"] is StringType


# ---------------------------------------------------------------------------
# Ingestion — reads the fixture file
# ---------------------------------------------------------------------------


def test_load_raw_users_reads_every_row(spark, users_xml):
    assert load_raw_users(spark, users_xml).count() == 5


def test_load_raw_users_applies_declared_schema(spark, users_xml):
    """The reader must use our schema, not infer one from the file."""
    assert load_raw_users(spark, users_xml).schema == USERS_SCHEMA


def test_a_wrong_row_tag_yields_no_rows_rather_than_an_error(spark, users_xml):
    """`rowTag` is the option that selects rows, and it fails silently.

    Worth pinning because the notebook read Users.xml with rootTag='posts' —
    copy-pasted from the posts notebook — and it worked anyway: on read,
    `rootTag` is ignored entirely. `rowTag` is the one that matters, and
    getting it wrong produces an empty DataFrame, not an exception. A pipeline
    that writes zero rows and reports success is the failure mode to know about.
    """
    assert load_raw_users(spark, users_xml, row_tag="notarow").count() == 0


def test_negative_ids_survive(spark, users_xml):
    """Id=-1 is the Community pseudo-user and is a real row in the dump.

    A filter or a cast that assumed positive ids would drop it, and it owns
    community-wiki posts — so the join in gold would lose them.
    """
    df = clean_columns(load_raw_users(spark, users_xml))

    assert df.filter(df.Id == -1).count() == 1


def test_missing_optional_attributes_read_as_null(spark, users_xml):
    """A user with no Location/WebsiteUrl/AboutMe must read as null, not ''.

    Bronze does not invent values. Distinguishing "absent" from "blank" is
    silver's business, and it can only make that call if bronze kept it.
    """
    df = clean_columns(load_raw_users(spark, users_xml))
    user = df.filter(df.Id == 15).collect()[0]

    assert user.Location is None
    assert user.WebsiteUrl is None
    assert user.AboutMe is None


def test_present_but_empty_attributes_are_not_null(spark, users_xml):
    """`WebsiteUrl=""` is present-and-blank, which is not the same as absent.

    The pair with the test above is the point: both cases exist in the real
    dump, and bronze must keep them apart.
    """
    df = clean_columns(load_raw_users(spark, users_xml))
    user = df.filter(df.Id == 42).collect()[0]

    assert user.WebsiteUrl == ""
    assert user.Location is None


def test_timestamps_are_stored_as_utc(spark, users_xml):
    """The stored instant must equal the source string, on any host machine.

    Formatted in Spark (session timezone = UTC, see ADR 0001) rather than
    collected into Python: `collect()` converts to the *host's* local timezone,
    so asserting on a Python datetime would pass or fail depending on who ran
    the suite — the exact class of bug ADR 0001 exists to prevent.
    """
    df = clean_columns(load_raw_users(spark, users_xml))
    formatted = (
        df.filter(df.Id == -1)
        .select(date_format("CreationDate", "yyyy-MM-dd'T'HH:mm:ss.SSS").alias("ts"))
        .collect()[0]
        .ts
    )

    assert formatted == "2016-08-02T00:14:10.580"


def test_run_writes_a_readable_delta_table(spark, users_xml):
    """End-to-end: ingest the fixture and read the result back."""
    spark.sql("CREATE DATABASE IF NOT EXISTS bronze_test")

    row_count = run(spark, source_path=users_xml, table="bronze_test.users")

    assert row_count == 5

    written = spark.table("bronze_test.users")
    assert written.count() == 5
    assert "Id" in written.columns
    assert not any(c.startswith("_") for c in written.columns)


def test_run_is_idempotent(spark, users_xml):
    """Re-running with mode=overwrite must not duplicate rows.

    A pipeline that doubles its data on retry is worse than one that fails.
    """
    spark.sql("CREATE DATABASE IF NOT EXISTS bronze_test")

    run(spark, source_path=users_xml, table="bronze_test.users_idem")
    run(spark, source_path=users_xml, table="bronze_test.users_idem")

    assert spark.table("bronze_test.users_idem").count() == 5


def test_user_ids_are_unique(spark, users_xml):
    """One row per user. A duplicate would fan out the join in gold.

    `marts_posts_users` joins posts to users on this key and must stay at one
    row per post; a duplicated user id silently multiplies rows instead of
    failing. The dbt `unique` test on `stg_users.user_id` is the downstream
    half of this guarantee.
    """
    df = clean_columns(load_raw_users(spark, users_xml))

    assert df.select("Id").distinct().count() == df.count()
