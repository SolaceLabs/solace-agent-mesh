"""
Tests for embed protection in Liquid template rendering.

These tests verify that embed directives (like «math:...») are properly
protected from Liquid template processing, preventing conflicts between
embed syntax and Liquid syntax.
"""

import pytest
import time
from solace_agent_mesh.common.utils.templates.liquid_renderer import (
    _protect_embeds_from_liquid,
    _restore_embeds_after_liquid,
    render_liquid_template,
    _EMBED_PROTECTION_REGEX,
)


class TestEmbedProtection:
    """Tests for the embed protection functions."""

    def test_protect_single_math_embed(self):
        """Test protecting a single math embed."""
        template = "Value: «math:42 | .2f»"
        protected, placeholders = _protect_embeds_from_liquid(template)
        
        assert "«math:" not in protected
        assert len(placeholders) == 1
        assert "«math:42 | .2f»" in placeholders.values()

    def test_protect_multiple_embeds(self):
        """Test protecting multiple embeds of different types."""
        template = "Math: «math:1+1» DateTime: «datetime:now» UUID: «uuid:»"
        protected, placeholders = _protect_embeds_from_liquid(template)
        
        assert "«math:" not in protected
        assert "«datetime:" not in protected
        assert "«uuid:" not in protected
        assert len(placeholders) == 3

    def test_protect_embed_with_liquid_syntax_inside(self):
        """Test protecting embeds that contain Liquid-like syntax."""
        # This is the problematic case from the bug
        template = "{% for row in data_rows %}| {{ row[0] }} | $«math:{{ row[2] }} | ,.2f» |{% endfor %}"
        protected, placeholders = _protect_embeds_from_liquid(template)
        
        # The embed should be replaced with a placeholder
        assert "«math:" not in protected
        assert len(placeholders) == 1
        # The Liquid syntax should remain
        assert "{% for row in data_rows %}" in protected
        assert "{{ row[0] }}" in protected

    def test_restore_embeds(self):
        """Test restoring embeds from placeholders."""
        original_embed = "«math:42 | .2f»"
        placeholder = "__EMBED_PLACEHOLDER_0__"
        placeholders = {placeholder: original_embed}
        
        rendered = f"Result: {placeholder}"
        restored = _restore_embeds_after_liquid(rendered, placeholders)
        
        assert restored == f"Result: {original_embed}"

    def test_protect_and_restore_roundtrip(self):
        """Test that protect and restore are inverse operations."""
        original = "Value: «math:42 | .2f» and «datetime:now»"
        protected, placeholders = _protect_embeds_from_liquid(original)
        restored = _restore_embeds_after_liquid(protected, placeholders)
        
        assert restored == original

    def test_no_embeds_returns_unchanged(self):
        """Test that text without embeds is unchanged."""
        template = "{% for item in items %}{{ item }}{% endfor %}"
        protected, placeholders = _protect_embeds_from_liquid(template)
        
        assert protected == template
        assert len(placeholders) == 0


class TestRenderLiquidTemplateWithEmbeds:
    """Integration tests for render_liquid_template with embeds."""

    def test_render_template_with_math_embed_in_loop(self):
        """Test rendering a template with math embeds inside a Liquid loop.
        
        The embeds are protected from Liquid processing, so the Liquid variables
        inside the embeds ({{ row[0] }}) remain as-is. The embed resolver will
        handle them later when processing the final output.
        """
        # This simulates the problematic case from the bug
        template = """| Header |
|--------|
{% for row in data_rows %}| $«math:{{ row[0] }} | ,.2f» |
{% endfor %}"""
        
        csv_data = "value\n100\n200\n300"
        
        rendered, error = render_liquid_template(
            template_content=template,
            data_artifact_content=csv_data,
            data_mime_type="text/csv",
        )
        
        assert error is None
        # The math embeds should be preserved (protected from Liquid)
        # The Liquid loop should still execute (3 rows)
        assert rendered.count("«math:{{ row[0] }} | ,.2f»") == 3
        # The table structure should be correct
        assert "| Header |" in rendered

    def test_render_template_with_multiple_embed_types(self):
        """Test rendering a template with multiple embed types.
        
        Embeds are protected from Liquid processing. The Liquid loop executes,
        but the embed content remains unchanged.
        """
        template = """Date: «datetime:now»
{% for item in items %}
- Value: «math:{{ item.value }} | .2f»
{% endfor %}"""
        
        json_data = '[{"value": 10}, {"value": 20}]'
        
        rendered, error = render_liquid_template(
            template_content=template,
            data_artifact_content=json_data,
            data_mime_type="application/json",
        )
        
        assert error is None
        # datetime embed should be preserved
        assert "«datetime:now»" in rendered
        # math embeds should be preserved (2 iterations of the loop)
        assert rendered.count("«math:{{ item.value }} | .2f»") == 2

    def test_render_template_without_embeds(self):
        """Test that templates without embeds still work correctly."""
        template = """{% for item in items %}
- {{ item.name }}: {{ item.value }}
{% endfor %}"""
        
        json_data = '[{"name": "A", "value": 1}, {"name": "B", "value": 2}]'
        
        rendered, error = render_liquid_template(
            template_content=template,
            data_artifact_content=json_data,
            data_mime_type="application/json",
        )
        
        assert error is None
        assert "A: 1" in rendered
        assert "B: 2" in rendered

    def test_render_markdown_table_with_embeds(self):
        """Test rendering a markdown table with math embeds - the exact bug scenario.
        
        Before the fix, this would fail because Liquid would try to interpret
        the | in «math:{{ row[1] }} | ,.2f» as a Liquid filter operator.
        
        After the fix, the embed is protected, so Liquid processes the rest
        of the template normally while leaving the embed intact.
        """
        template = """| Payment Method | Total Revenue |
|----------------|---------------|
{% for row in data_rows %}| {{ row[0] }} | $«math:{{ row[1] }} | ,.2f» |
{% endfor %}"""
        
        csv_data = "method,revenue\nCash,1000.50\nCredit,2500.75"
        
        rendered, error = render_liquid_template(
            template_content=template,
            data_artifact_content=csv_data,
            data_mime_type="text/csv",
        )
        
        assert error is None
        # Check that the table structure is correct - Liquid variables outside embeds are processed
        assert "| Cash |" in rendered
        assert "| Credit |" in rendered
        # Check that math embeds are preserved (protected from Liquid)
        assert rendered.count("«math:{{ row[1] }} | ,.2f»") == 2

    def test_render_template_with_static_math_embed(self):
        """Test rendering a template with static math embeds (no Liquid variables inside)."""
        template = """Result: «math:42 * 2 | .2f»
{% for item in items %}
- {{ item.name }}
{% endfor %}"""
        
        json_data = '[{"name": "A"}, {"name": "B"}]'
        
        rendered, error = render_liquid_template(
            template_content=template,
            data_artifact_content=json_data,
            data_mime_type="application/json",
        )
        
        assert error is None
        # Static math embed should be preserved
        assert "«math:42 * 2 | .2f»" in rendered
        # Liquid loop should work
        assert "- A" in rendered
        assert "- B" in rendered

    def test_render_fails_without_protection(self):
        """Verify that without protection, Liquid would fail on pipe character.
        
        This test documents the bug that the protection fixes.
        The pipe character in the embed would be interpreted as a Liquid filter.
        """
        # This template has a pipe character that Liquid would try to interpret as a filter
        template_with_pipe_in_embed = "Value: «math:42 | .2f»"
        
        # With protection, this should work
        rendered, error = render_liquid_template(
            template_content=template_with_pipe_in_embed,
            data_artifact_content="{}",
            data_mime_type="application/json",
        )
        
        assert error is None
        assert "«math:42 | .2f»" in rendered


class TestRegexSafety:
    """Tests for regex safety to prevent ReDoS attacks."""

    def test_regex_handles_unclosed_embed(self):
        """Test that unclosed embeds don't cause catastrophic backtracking."""
        # An unclosed embed should not match and should not cause performance issues
        template = "Value: «math:42 without closing delimiter"
        
        start_time = time.time()
        protected, placeholders = _protect_embeds_from_liquid(template)
        elapsed = time.time() - start_time
        
        # Should complete quickly (< 1 second)
        assert elapsed < 1.0
        # No embeds should be matched
        assert len(placeholders) == 0
        # Template should be unchanged
        assert protected == template

    def test_regex_handles_long_content(self):
        """Test that long content doesn't cause performance issues."""
        # Create a template with a long expression inside an embed
        long_expression = "a" * 5000
        template = f"Value: «math:{long_expression}»"
        
        start_time = time.time()
        protected, placeholders = _protect_embeds_from_liquid(template)
        elapsed = time.time() - start_time
        
        # Should complete quickly (< 1 second)
        assert elapsed < 1.0
        # The embed should be matched
        assert len(placeholders) == 1

    def test_regex_respects_length_limit(self):
        """Test that expressions exceeding the length limit are not matched."""
        # Create an expression that exceeds the 10000 char limit
        very_long_expression = "a" * 15000
        template = f"Value: «math:{very_long_expression}»"
        
        protected, placeholders = _protect_embeds_from_liquid(template)
        
        # The embed should NOT be matched due to length limit
        assert len(placeholders) == 0
        # Template should be unchanged
        assert protected == template

    def test_regex_handles_nested_delimiters(self):
        """Test that nested-looking patterns don't cause issues."""
        # This shouldn't match because the inner « is not followed by a type:
        template = "Value: «math:test « inner » test»"
        
        start_time = time.time()
        protected, placeholders = _protect_embeds_from_liquid(template)
        elapsed = time.time() - start_time
        
        # Should complete quickly
        assert elapsed < 1.0
        # Should match the outer embed (up to first »)
        assert len(placeholders) == 1

    def test_regex_pattern_is_safe(self):
        """Verify the regex pattern uses safe constructs."""
        pattern_str = _EMBED_PROTECTION_REGEX.pattern
        
        # Should NOT contain dangerous patterns like .*+ or nested quantifiers
        assert ".*+" not in pattern_str
        assert ".++" not in pattern_str
        # Should use negated character class for safety
        assert "[^" in pattern_str
        # Should have a length limit
        assert "{0,10000}" in pattern_str
