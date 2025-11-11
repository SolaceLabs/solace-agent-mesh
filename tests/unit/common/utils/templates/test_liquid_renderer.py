"""
Unit tests for Liquid template rendering.
"""

from solace_agent_mesh.common.utils.templates import render_liquid_template


def test_render_simple_dict():
    """Test rendering a simple dictionary context."""
    template = "Hello, {{ name }}! You are {{ age }} years old."
    data = {"name": "Alice", "age": 30}

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
    )

    assert error is None
    assert output == "Hello, Alice! You are 30 years old."


def test_render_list_as_items():
    """Test rendering a list (should be available as 'items')."""
    template = "{% for item in items %}{{ item.name }}, {% endfor %}"
    data = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
    )

    assert error is None
    assert "Alice" in output
    assert "Bob" in output
    assert "Charlie" in output


def test_render_csv_with_headers_and_rows():
    """Test rendering CSV data with headers and data_rows."""
    template = (
        "| {% for h in headers %}{{ h }} | {% endfor %}\n"
        "{% for row in data_rows %}"
        "| {% for cell in row %}{{ cell }} | {% endfor %}\n"
        "{% endfor %}"
    )
    csv_data = "Name,Age,City\nAlice,30,NYC\nBob,25,LA"

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=csv_data,
        data_mime_type="text/csv",
    )

    assert error is None
    assert "Name" in output
    assert "Age" in output
    assert "Alice" in output
    assert "Bob" in output


def test_render_with_jsonpath():
    """Test rendering with JSONPath filtering."""
    template = "{% for user in items %}{{ user.name }}, {% endfor %}"
    data = {
        "users": [{"name": "Alice", "active": True}, {"name": "Bob", "active": False}],
        "count": 2,
    }

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
        jsonpath="$.users[?@.active==true]",
    )

    assert error is None
    assert "Alice" in output
    assert "Bob" not in output


def test_render_with_limit():
    """Test rendering with limit parameter."""
    template = "{% for item in items %}{{ item }}, {% endfor %}"
    data = ["A", "B", "C", "D", "E"]

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
        limit=3,
    )

    assert error is None
    assert "A" in output
    assert "B" in output
    assert "C" in output
    assert "D" not in output
    assert "E" not in output


def test_render_csv_with_limit():
    """Test rendering CSV with limit on rows."""
    template = "{% for row in data_rows %}Row: {% for cell in row %}{{ cell }} {% endfor %}\n{% endfor %}"
    csv_data = "Name,Age\nAlice,30\nBob,25\nCharlie,35"

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=csv_data,
        data_mime_type="text/csv",
        limit=2,
    )

    assert error is None
    assert "Alice" in output
    assert "Bob" in output
    assert "Charlie" not in output


def test_render_primitive_value():
    """Test rendering a primitive value (available as 'value')."""
    template = "The answer is: {{ value }}"
    data = 42

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
    )

    assert error is None
    assert "The answer is: 42" in output


def test_render_with_invalid_template():
    """Test handling of invalid Liquid template syntax."""
    template = "{% for item in items }{{ item }}{% endfor %}"  # Missing closing tag
    data = [1, 2, 3]

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
    )

    # Should return error
    assert error is not None
    assert "Template Error" in output


def test_render_with_invalid_jsonpath():
    """Test handling of invalid JSONPath expression."""
    template = "{{ value }}"
    data = {"key": "value"}

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
        jsonpath="$.invalid[[[",  # Invalid JSONPath
    )

    # Should return error
    assert error is not None
    assert "Template Error" in output


def test_render_yaml_data():
    """Test rendering YAML data."""
    template = "Server: {{ server.host }}:{{ server.port }}"
    yaml_data = {"server": {"host": "localhost", "port": 8080}}

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=yaml_data,
        data_mime_type="application/yaml",
    )

    assert error is None
    assert "Server: localhost:8080" in output


def test_render_complex_liquid_template():
    """Test a more complex Liquid template with conditionals and loops."""
    template = """
{% if items %}
Active Users:
{% for user in items %}
  {% if user.active %}
  - {{ user.name }} ({{ user.email }})
  {% endif %}
{% endfor %}
{% else %}
No users found.
{% endif %}
"""
    data = [
        {"name": "Alice", "email": "alice@example.com", "active": True},
        {"name": "Bob", "email": "bob@example.com", "active": False},
        {"name": "Charlie", "email": "charlie@example.com", "active": True},
    ]

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
    )

    assert error is None
    assert "Alice" in output
    assert "alice@example.com" in output
    assert "Bob" not in output  # Bob is inactive
    assert "Charlie" in output


def test_render_with_jsonpath_and_limit():
    """Test combining JSONPath and limit."""
    template = "{% for item in items %}{{ item.name }}, {% endfor %}"
    data = {
        "products": [
            {"name": "A", "price": 10},
            {"name": "B", "price": 20},
            {"name": "C", "price": 30},
            {"name": "D", "price": 40},
        ]
    }

    output, error = render_liquid_template(
        template_content=template,
        data_artifact_content=data,
        data_mime_type="application/json",
        jsonpath="$.products",
        limit=2,
    )

    assert error is None
    assert "A" in output
    assert "B" in output
    assert "C" not in output
    assert "D" not in output
