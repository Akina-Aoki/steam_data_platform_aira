
{# dbt uses this macro to choose the schema where a model's data is stored. #}
{% macro generate_schema_name(custom_schema_name, node) -%}

    {# If the model has its own schema name configured, use it. #}
    {%- if custom_schema_name is not none -%}
        {# trim removes any accidental spaces from the start or end of that name. #}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {# If not, use the schema from the active dbt target (such as dev or prod). #}
        {{ target.schema }}
    {%- endif -%}

{%- endmacro %}
