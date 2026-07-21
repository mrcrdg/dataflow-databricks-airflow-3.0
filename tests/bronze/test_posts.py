"""Tests for bronze posts ingestion.

Split deliberately into two kinds:

1. Pure transformation tests — no I/O, fast, the bulk of the value.
2. Ingestion tests — read the fixture file, exercise the reader and writer.

If a change breaks the pure tests, the logic is wrong. If it only breaks the
ingestion tests, the plumbing is wrong. Keeping them separate makes failures
diagnostic rather than just red.
"""

from __future__ import annotations

from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

from dataflow.bronze.posts import (
    POSTS_SCHEMA,
    clean_columns,
    load_raw_posts,
    run,
)

# ---------------------------------------------------------------------------
# Schema — the data contract for the bronze layer
# ---------------------------------------------------------------------------


def test_schema_declares_all_source_attributes():
    """The Stack Exchange Posts dump has 22 attributes; all must be declared.

    Guards against a field being dropped during a refactor, which would
    silently discard a column rather than fail loudly.
    """
    assert len(POSTS_SCHEMA.fields) == 22


def test_schema_field_names_match_xml_attribute_form():
    """Every declared field carries the leading underscore the XML reader adds.

    Spark's XML reader prefixes attributes with '_'. If a field here were
    written without it, that column would silently read as all-null.
    """
    assert all(f.name.startswith("_") for f in POSTS_SCHEMA.fields)


def test_schema_types_are_explicit_not_inferred():
    """Key columns must keep their declared types.

    Ids are Long, dates are Timestamp. If these degrade to String, downstream
    joins and date filters break in ways that are hard to trace.
    """
    types = {f.name: type(f.dataType) for f in POSTS_SCHEMA.fields}

    assert types["_Id"] is LongType
    assert types["_OwnerUserId"] is LongType
    assert types["_CreationDate"] is TimestampType
    assert types["_Title"] is StringType


# ---------------------------------------------------------------------------
# clean_columns — pure transformation, no Spark I/O
# ---------------------------------------------------------------------------


def test_clean_columns_strips_leading_underscore(spark):
    df = spark.createDataFrame([(1, "hello")], schema=StructType([
        StructField("_Id", LongType()),
        StructField("_Title", StringType()),
    ]))

    assert clean_columns(df).columns == ["Id", "Title"]


def test_clean_columns_preserves_rows_and_values(spark):
    """Renaming columns must not touch the data itself."""
    df = spark.createDataFrame([(1, "a"), (2, "b")], schema=StructType([
        StructField("_Id", LongType()),
        StructField("_Title", StringType()),
    ]))

    cleaned = clean_columns(df)

    assert cleaned.count() == 2
    assert [r.Id for r in cleaned.orderBy("Id").collect()] == [1, 2]


def test_clean_columns_leaves_clean_names_untouched(spark):
    """Idempotent: running it on already-clean columns changes nothing.

    Matters because a re-run of the pipeline must not mangle names further.
    """
    df = spark.createDataFrame([(1,)], schema=StructType([StructField("Id", LongType())]))

    assert clean_columns(df).columns == ["Id"]


def test_clean_columns_only_strips_leading_underscores(spark):
    """Internal underscores are part of the name and must survive.

    The original implementation used replace("_", ""), which would have turned
    'user_id' into 'userid'. No source column has an internal underscore today,
    so this test protects a property that is currently untested by the data.
    """
    df = spark.createDataFrame([(1,)], schema=StructType([StructField("_user_id", LongType())]))

    assert clean_columns(df).columns == ["user_id"]


# ---------------------------------------------------------------------------
# Ingestion — reads the fixture file
# ---------------------------------------------------------------------------


def test_load_raw_posts_reads_every_row(spark, posts_xml):
    assert load_raw_posts(spark, posts_xml).count() == 5


def test_load_raw_posts_applies_declared_schema(spark, posts_xml):
    """The reader must use our schema, not infer one from the file."""
    assert load_raw_posts(spark, posts_xml).schema == POSTS_SCHEMA


def test_answers_have_no_title_or_tags(spark, posts_xml):
    """Answers (PostTypeId=2) carry no Title or Tags — they must read as null.

    This is the shape silver has to handle, so bronze must not invent values.
    """
    df = clean_columns(load_raw_posts(spark, posts_xml))
    answers = df.filter(df.PostTypeId == 2).collect()

    assert len(answers) == 1
    assert answers[0].Title is None
    assert answers[0].Tags is None


def test_questions_keep_pipe_delimited_tags(spark, posts_xml):
    """Bronze stores tags exactly as the source has them: |a|b|c|.

    Splitting them is silver's job. Bronze stays a faithful copy.
    """
    df = clean_columns(load_raw_posts(spark, posts_xml))
    tags = df.filter(df.Id == 1).collect()[0].Tags

    assert tags.startswith("|") and tags.endswith("|")
    assert "neural-networks" in tags


def test_run_writes_a_readable_delta_table(spark, posts_xml):
    """End-to-end: ingest the fixture and read the result back."""
    spark.sql("CREATE DATABASE IF NOT EXISTS bronze_test")

    row_count = run(spark, source_path=posts_xml, table="bronze_test.posts")

    assert row_count == 5

    written = spark.table("bronze_test.posts")
    assert written.count() == 5
    assert "Id" in written.columns
    assert not any(c.startswith("_") for c in written.columns)


def test_run_is_idempotent(spark, posts_xml):
    """Re-running with mode=overwrite must not duplicate rows.

    A pipeline that doubles its data on retry is worse than one that fails.
    """
    spark.sql("CREATE DATABASE IF NOT EXISTS bronze_test")

    run(spark, source_path=posts_xml, table="bronze_test.posts_idem")
    run(spark, source_path=posts_xml, table="bronze_test.posts_idem")

    assert spark.table("bronze_test.posts_idem").count() == 5
