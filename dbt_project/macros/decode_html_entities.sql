{% macro decode_html_entities(column_name) %}
    {# Turn HTML-encoded quotes (&quot;) and ampersands (&amp;) back into normal characters. #}
    {# Pass a column name, such as "description"; this macro creates SQL that cleans its values. #}
    replace(replace({{ column_name }}, '&quot;', '"'), '&amp;', '&')
{% endmacro %}