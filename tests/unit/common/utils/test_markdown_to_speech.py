"""
Unit tests for markdown_to_speech utility.

Tests the conversion of markdown-formatted text to natural speech-friendly text.
"""

import pytest
from solace_agent_mesh.common.utils.markdown_to_speech import (
    markdown_to_speech,
    MarkdownToSpeechOptions,
)


class TestBasicMarkdownRemoval:
    """Tests for basic markdown syntax removal."""

    def test_removes_bold_double_asterisk(self):
        """Test removal of **bold** markers."""
        assert markdown_to_speech("This is **bold** text") == "This is bold text"

    def test_removes_bold_double_underscore(self):
        """Test removal of __bold__ markers."""
        assert markdown_to_speech("This is __bold__ text") == "This is bold text"

    def test_removes_italic_single_asterisk(self):
        """Test removal of *italic* markers."""
        assert markdown_to_speech("This is *italic* text") == "This is italic text"

    def test_removes_italic_single_underscore(self):
        """Test removal of _italic_ markers."""
        assert markdown_to_speech("This is _italic_ text") == "This is italic text"

    def test_removes_strikethrough(self):
        """Test removal of ~~strikethrough~~ markers."""
        assert markdown_to_speech("This is ~~deleted~~ text") == "This is deleted text"

    def test_preserves_underscores_in_words(self):
        """Test that underscores in snake_case are preserved."""
        result = markdown_to_speech("Use the variable_name here")
        assert "variable_name" in result

    def test_handles_nested_formatting(self):
        """Test handling of nested bold and italic."""
        result = markdown_to_speech("This is ***bold and italic*** text")
        assert "***" not in result
        assert "bold" in result


class TestLinkHandling:
    """Tests for link markdown handling."""

    def test_extracts_link_text(self):
        """Test extraction of link text from [text](url)."""
        assert markdown_to_speech("Click [here](https://example.com)") == "Click here"

    def test_extracts_link_text_with_title(self):
        """Test extraction of link text with title."""
        result = markdown_to_speech('Visit [our site](https://example.com "Title")')
        assert "our site" in result
        assert "https://" not in result

    def test_handles_multiple_links(self):
        """Test handling of multiple links in text."""
        text = "See [link1](url1) and [link2](url2)"
        result = markdown_to_speech(text)
        assert "link1" in result
        assert "link2" in result
        assert "url1" not in result
        assert "url2" not in result

    def test_handles_bare_urls(self):
        """Test that bare URLs are replaced with 'link'."""
        result = markdown_to_speech("Visit https://example.com for more")
        assert "https://" not in result
        assert "link" in result


class TestImageHandling:
    """Tests for image markdown handling."""

    def test_announces_images_by_default(self):
        """Test that images are announced with alt text."""
        result = markdown_to_speech("![A cat](image.jpg)")
        assert "Image:" in result
        assert "A cat" in result
        assert "image.jpg" not in result

    def test_skips_images_when_disabled(self):
        """Test that images can be skipped entirely."""
        options = MarkdownToSpeechOptions(read_images=False)
        result = markdown_to_speech("![A cat](image.jpg)", options)
        assert "Image:" not in result
        assert "A cat" not in result

    def test_handles_empty_alt_text(self):
        """Test handling of images with empty alt text."""
        result = markdown_to_speech("![](image.jpg)")
        # Should not crash, may or may not include "Image:"
        assert "image.jpg" not in result


class TestCodeHandling:
    """Tests for code markdown handling."""

    def test_removes_inline_code_backticks(self):
        """Test removal of `inline code` backticks."""
        assert markdown_to_speech("Use the `print()` function") == "Use the print() function"

    def test_removes_code_blocks_by_default(self):
        """Test that code blocks are removed by default."""
        text = """Here is code:
```python
print("hello")
```
End of code."""
        result = markdown_to_speech(text)
        assert "```" not in result
        assert "print" not in result

    def test_announces_code_blocks_when_enabled(self):
        """Test that code blocks can be announced."""
        options = MarkdownToSpeechOptions(read_code_blocks=True)
        text = """Here is code:
```python
print("hello")
```
End."""
        result = markdown_to_speech(text, options)
        assert "Code block" in result


class TestHeaderHandling:
    """Tests for header markdown handling."""

    def test_removes_h1_marker(self):
        """Test removal of # header marker."""
        result = markdown_to_speech("# Main Title")
        assert "#" not in result
        assert "Main Title" in result

    def test_removes_h2_marker(self):
        """Test removal of ## header marker."""
        result = markdown_to_speech("## Section")
        assert "##" not in result
        assert "Section" in result

    def test_removes_h3_to_h6_markers(self):
        """Test removal of ### to ###### markers."""
        for i in range(3, 7):
            marker = "#" * i
            result = markdown_to_speech(f"{marker} Header Level {i}")
            assert marker not in result
            assert f"Header Level {i}" in result

    def test_adds_pause_after_headers(self):
        """Test that headers get a pause (period) by default."""
        result = markdown_to_speech("# Title\n\nContent here")
        # Should have period after title
        assert "Title." in result or "Title ." in result or result.startswith("Title.")


class TestListHandling:
    """Tests for list markdown handling."""

    def test_removes_unordered_list_dash(self):
        """Test removal of - list markers."""
        result = markdown_to_speech("- Item one\n- Item two")
        assert "-" not in result or result.count("-") == 0
        assert "Item one" in result
        assert "Item two" in result

    def test_removes_unordered_list_asterisk(self):
        """Test removal of * list markers."""
        result = markdown_to_speech("* Item one\n* Item two")
        assert "Item one" in result

    def test_keeps_ordered_list_numbers(self):
        """Test that ordered list numbers are kept for context."""
        result = markdown_to_speech("1. First\n2. Second")
        assert "1" in result
        assert "2" in result
        assert "First" in result
        assert "Second" in result


class TestBlockquoteHandling:
    """Tests for blockquote markdown handling."""

    def test_removes_blockquote_marker(self):
        """Test removal of > blockquote marker."""
        result = markdown_to_speech("> This is a quote")
        assert ">" not in result
        assert "This is a quote" in result

    def test_handles_nested_blockquotes(self):
        """Test handling of nested blockquotes."""
        result = markdown_to_speech(">> Nested quote")
        assert ">>" not in result
        assert "Nested quote" in result


class TestHorizontalRuleHandling:
    """Tests for horizontal rule handling."""

    def test_removes_dash_horizontal_rule(self):
        """Test removal of --- horizontal rule."""
        result = markdown_to_speech("Before\n\n---\n\nAfter")
        assert "---" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_asterisk_horizontal_rule(self):
        """Test removal of *** horizontal rule."""
        result = markdown_to_speech("Before\n\n***\n\nAfter")
        assert "***" not in result


class TestCitationHandling:
    """Tests for citation reference handling."""

    def test_reads_citations_by_default(self):
        """Test that citations are read as 'reference N'."""
        result = markdown_to_speech("According to research [1]")
        assert "[1]" not in result
        assert "reference 1" in result

    def test_handles_multiple_citations(self):
        """Test handling of multiple citations."""
        result = markdown_to_speech("Studies [1] and [2] show")
        assert "[1]" not in result
        assert "[2]" not in result
        assert "reference 1" in result
        assert "reference 2" in result

    def test_skips_citations_when_disabled(self):
        """Test that citations can be skipped."""
        options = MarkdownToSpeechOptions(read_citations=False)
        result = markdown_to_speech("Research [1] shows", options)
        assert "[1]" not in result
        assert "reference" not in result

    def test_custom_citation_format(self):
        """Test custom citation format."""
        options = MarkdownToSpeechOptions(citation_format="citation {n}")
        result = markdown_to_speech("Study [1]", options)
        assert "citation 1" in result


class TestSAMCitationHandling:
    """Tests for SAM-style citation handling (web search, deep research)."""

    def test_handles_search_citation(self):
        """Test handling of [[cite:search0]] format."""
        result = markdown_to_speech("According to research [[cite:search0]]")
        assert "[[cite:search0]]" not in result
        assert "source 1" in result  # 0-indexed becomes 1-indexed

    def test_handles_research_citation(self):
        """Test handling of [[cite:research0]] format."""
        result = markdown_to_speech("Deep research shows [[cite:research0]]")
        assert "[[cite:research0]]" not in result
        assert "research source 1" in result

    def test_handles_file_citation(self):
        """Test handling of [[cite:file0]] format."""
        result = markdown_to_speech("See document [[cite:file0]]")
        assert "[[cite:file0]]" not in result
        assert "file 1" in result

    def test_handles_ref_citation(self):
        """Test handling of [[cite:ref0]] format."""
        result = markdown_to_speech("Reference [[cite:ref0]]")
        assert "[[cite:ref0]]" not in result
        assert "reference 1" in result

    def test_handles_citation_without_type(self):
        """Test handling of [[cite:0]] format (defaults to search)."""
        result = markdown_to_speech("See [[cite:0]]")
        assert "[[cite:0]]" not in result
        assert "source 1" in result

    def test_handles_single_bracket_citation(self):
        """Test handling of [cite:search0] format (single bracket variant)."""
        result = markdown_to_speech("See [cite:search0]")
        assert "[cite:search0]" not in result
        assert "source 1" in result

    def test_handles_multi_citation_same_type(self):
        """Test handling of [[cite:search0, search1, search2]] format."""
        result = markdown_to_speech("Multiple sources [[cite:search0, search1, search2]]")
        assert "[[cite:" not in result
        assert "source 1" in result
        assert "source 2" in result
        assert "source 3" in result
        assert "and" in result  # Should use "and" for last item

    def test_handles_multi_citation_with_cite_prefix(self):
        """Test handling of [[cite:research0, cite:research1]] format."""
        result = markdown_to_speech("Research [[cite:research0, cite:research1]]")
        assert "[[cite:" not in result
        assert "research source 1" in result
        assert "research source 2" in result

    def test_handles_two_citations(self):
        """Test handling of two citations uses 'and' correctly."""
        result = markdown_to_speech("See [[cite:search0, search1]]")
        assert "source 1 and source 2" in result

    def test_handles_mixed_citation_types(self):
        """Test handling of mixed citation types in multi-citation."""
        result = markdown_to_speech("See [[cite:search0, research1]]")
        assert "source 1" in result
        assert "research source 2" in result

    def test_skips_sam_citations_when_disabled(self):
        """Test that SAM citations are removed when read_citations is False."""
        options = MarkdownToSpeechOptions(read_citations=False)
        result = markdown_to_speech("Research [[cite:search0]] shows", options)
        assert "[[cite:" not in result
        assert "source" not in result

    def test_handles_multiple_separate_citations(self):
        """Test handling of multiple separate SAM citations in text."""
        result = markdown_to_speech("First [[cite:search0]] and second [[cite:research1]]")
        assert "[[cite:" not in result
        assert "source 1" in result
        assert "research source 2" in result

    def test_complex_text_with_sam_citations(self):
        """Test complex text with SAM citations and other markdown."""
        text = """# Research Summary

According to **multiple studies** [[cite:search0, search1]], the results show:

- Finding one [[cite:research0]]
- Finding two [[cite:research1]]

For more details, see [the documentation](https://example.com) [[cite:file0]].
"""
        result = markdown_to_speech(text)
        
        # Should not contain markdown syntax
        assert "**" not in result
        assert "[[cite:" not in result
        assert "#" not in result
        assert "https://" not in result
        
        # Should contain spoken citations
        assert "source 1" in result
        assert "source 2" in result
        assert "research source 1" in result
        assert "research source 2" in result
        assert "file 1" in result
        
        # Should contain content
        assert "Research Summary" in result
        assert "multiple studies" in result


class TestWebSearchCitationFormat:
    """Tests for web search citation format (s#r# pattern)."""

    def test_handles_s1r1_citation(self):
        """Test handling of [[cite:s1r1]] format."""
        result = markdown_to_speech("See [[cite:s1r1]]")
        assert "[[cite:s1r1]]" not in result
        assert "search 1 result 1" in result

    def test_handles_s2r3_citation(self):
        """Test handling of [[cite:s2r3]] format."""
        result = markdown_to_speech("See [[cite:s2r3]]")
        assert "[[cite:s2r3]]" not in result
        assert "search 2 result 3" in result

    def test_handles_single_bracket_web_search(self):
        """Test handling of [cite:s1r1] format (single bracket)."""
        result = markdown_to_speech("See [cite:s1r1]")
        assert "[cite:s1r1]" not in result
        assert "search 1 result 1" in result

    def test_handles_multiple_web_search_citations(self):
        """Test handling of multiple web search citations."""
        result = markdown_to_speech("First [[cite:s1r1]] and second [[cite:s2r3]]")
        assert "[[cite:" not in result
        assert "search 1 result 1" in result
        assert "search 2 result 3" in result

    def test_handles_mixed_web_search_and_sam_citations(self):
        """Test handling of mixed web search and SAM citation formats."""
        result = markdown_to_speech("Web [[cite:s1r1]] and research [[cite:research0]]")
        assert "[[cite:" not in result
        assert "search 1 result 1" in result
        assert "research source 1" in result

    def test_skips_web_search_citations_when_disabled(self):
        """Test that web search citations are removed when read_citations is False."""
        options = MarkdownToSpeechOptions(read_citations=False)
        result = markdown_to_speech("See [[cite:s1r1]]", options)
        assert "[[cite:" not in result
        assert "search" not in result

    def test_complex_text_with_web_search_citations(self):
        """Test complex text with web search citations."""
        text = """According to the search results [[cite:s1r1]], the weather is sunny.
        
Another source [[cite:s2r3]] confirms this finding. See also [[cite:s1r2]] for more details."""
        result = markdown_to_speech(text)
        
        # Should not contain citation markers
        assert "[[cite:" not in result
        
        # Should contain spoken citations
        assert "search 1 result 1" in result
        assert "search 2 result 3" in result
        assert "search 1 result 2" in result
        
        # Should contain content
        assert "weather is sunny" in result
        assert "confirms this finding" in result


class TestTableHandling:
    """Tests for table markdown handling."""

    def test_extracts_table_content(self):
        """Test extraction of text from tables."""
        table = """| Name | Age |
|------|-----|
| John | 30  |
| Jane | 25  |"""
        result = markdown_to_speech(table)
        assert "|" not in result
        assert "---" not in result
        assert "Name" in result
        assert "John" in result

    def test_handles_simple_table(self):
        """Test handling of simple table."""
        table = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = markdown_to_speech(table)
        assert "A" in result
        assert "1" in result


class TestHTMLHandling:
    """Tests for HTML tag handling."""

    def test_strips_html_tags(self):
        """Test removal of HTML tags."""
        result = markdown_to_speech("This is <strong>bold</strong> text")
        assert "<strong>" not in result
        assert "</strong>" not in result
        assert "bold" in result

    def test_strips_html_comments(self):
        """Test removal of HTML comments."""
        result = markdown_to_speech("Text <!-- comment --> here")
        assert "<!--" not in result
        assert "-->" not in result
        assert "comment" not in result

    def test_decodes_html_entities(self):
        """Test decoding of HTML entities."""
        result = markdown_to_speech("Tom &amp; Jerry")
        assert "&amp;" not in result
        assert "&" in result

    def test_decodes_common_entities(self):
        """Test decoding of common HTML entities."""
        result = markdown_to_speech("&lt;tag&gt; and &quot;quoted&quot;")
        assert "<tag>" in result
        assert '"quoted"' in result


class TestWhitespaceNormalization:
    """Tests for whitespace normalization."""

    def test_normalizes_multiple_newlines(self):
        """Test that multiple newlines become single space."""
        result = markdown_to_speech("First\n\n\n\nSecond")
        assert "\n\n\n\n" not in result
        assert "First" in result
        assert "Second" in result

    def test_normalizes_multiple_spaces(self):
        """Test that multiple spaces become single space."""
        result = markdown_to_speech("Word    word")
        assert "    " not in result

    def test_trims_result(self):
        """Test that result is trimmed."""
        result = markdown_to_speech("  Text  ")
        assert result == "Text" or not result.startswith(" ")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_string(self):
        """Test handling of empty string."""
        assert markdown_to_speech("") == ""

    def test_none_like_empty(self):
        """Test handling of whitespace-only string."""
        result = markdown_to_speech("   ")
        assert result == ""

    def test_plain_text_unchanged(self):
        """Test that plain text without markdown is mostly unchanged."""
        text = "This is plain text without any markdown."
        result = markdown_to_speech(text)
        assert "plain text" in result
        assert "markdown" in result

    def test_complex_markdown(self):
        """Test handling of complex markdown document."""
        text = """# Welcome

This is **important** information about [our product](https://example.com).

## Features

- Feature one
- Feature two

> Note: This is a quote

```python
code example
```

According to research [1], this works.
"""
        result = markdown_to_speech(text)
        
        # Should not contain markdown syntax
        assert "**" not in result
        assert "##" not in result
        assert "```" not in result
        assert "[1]" not in result
        assert "https://" not in result
        
        # Should contain the actual content
        assert "Welcome" in result
        assert "important" in result
        assert "our product" in result
        assert "Feature one" in result


class TestOptionsConfiguration:
    """Tests for configuration options."""

    def test_default_options(self):
        """Test that default options work correctly."""
        options = MarkdownToSpeechOptions()
        assert options.read_code_blocks is False
        assert options.read_images is True
        assert options.read_citations is True
        assert options.add_header_pauses is True

    def test_custom_code_block_prefix(self):
        """Test custom code block prefix."""
        options = MarkdownToSpeechOptions(
            read_code_blocks=True,
            code_block_prefix="Code example."
        )
        text = "```\ncode\n```"
        result = markdown_to_speech(text, options)
        assert "Code example" in result

    def test_custom_image_prefix(self):
        """Test custom image prefix."""
        options = MarkdownToSpeechOptions(image_prefix="Picture:")
        result = markdown_to_speech("![cat](cat.jpg)", options)
        assert "Picture:" in result
