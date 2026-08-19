{#
    Cross-dialect helpers.

    The project claims Databricks is "an adapter swap, not a rewrite" (ADR 0005).
    That claim was never tested, and it was not quite true: three DuckDB-only
    constructs appeared in the models. These macros are what makes it true —
    each one dispatches on the adapter, so a model reads the same on either
    target and dbt picks the dialect.

    Nothing else in the models is DuckDB-specific. Identifier quoting was: the
    bronze columns arrive from the XML reader as `Id`, `PostTypeId`, and the
    models quoted them (`p."Id"`). Databricks SQL reads a double-quoted token as
    a string literal, not an identifier. Both engines match unquoted identifiers
    case-insensitively, so the quotes were removed rather than macro'd.
#}

{# Split a delimited string into an array.
   DuckDB's string_split takes a literal delimiter; Databricks' split takes a
   regular expression, so the delimiter has to be escaped there. #}
{% macro split_string(column, delimiter) -%}
    {{ return(adapter.dispatch('split_string', 'dataflow')(column, delimiter)) }}
{%- endmacro %}

{% macro default__split_string(column, delimiter) -%}
    string_split({{ column }}, '{{ delimiter }}')
{%- endmacro %}

{% macro databricks__split_string(column, delimiter) -%}
    split({{ column }}, '\\{{ delimiter }}')
{%- endmacro %}


{# Drop empty strings from an array. Same lambda syntax, different function. #}
{% macro filter_non_empty(array_expression) -%}
    {{ return(adapter.dispatch('filter_non_empty', 'dataflow')(array_expression)) }}
{%- endmacro %}

{% macro default__filter_non_empty(array_expression) -%}
    list_filter({{ array_expression }}, x -> x <> '')
{%- endmacro %}

{% macro databricks__filter_non_empty(array_expression) -%}
    filter({{ array_expression }}, x -> x <> '')
{%- endmacro %}


{# One row per array element, in the select list.
   The notebooks originally used Hive's LATERAL VIEW explode; on Databricks the
   wheel turns back to explode(), which is what that syntax became. #}
{% macro unnest_array(column) -%}
    {{ return(adapter.dispatch('unnest_array', 'dataflow')(column)) }}
{%- endmacro %}

{% macro default__unnest_array(column) -%}
    unnest({{ column }})
{%- endmacro %}

{% macro databricks__unnest_array(column) -%}
    explode({{ column }})
{%- endmacro %}
