"""
Markdown to Speech Preprocessor

Converts markdown-formatted text to natural, speakable text suitable for
Text-to-Speech (TTS) engines.

Uses markdown-it-py for robust markdown parsing and BeautifulSoup for
HTML text extraction.
"""
import re
import html
from typing import Optional
from dataclasses import dataclass

# Maximum input length to prevent resource exhaustion (100KB)
# This matches the limit in stream_speech API endpoint
MAX_INPUT_LENGTH = 100 * 1024


@dataclass
class MarkdownToSpeechOptions:
    """Configuration options for markdown to speech conversion."""

    # Whether to announce code blocks (e.g., "Code block: print hello")
    read_code_blocks: bool = False

    # Whether to announce images (e.g., "Image: description")
    read_images: bool = True

    # Whether to read citation references like [1], [2]
    read_citations: bool = True

    # Format for citations. Use {n} as placeholder for the number
    # Set to empty string to skip citations entirely
    citation_format: str = "reference {n}"

    # Whether to add pauses (periods) after headers
    add_header_pauses: bool = True

    # Prefix for code blocks when read_code_blocks is True
    code_block_prefix: str = "Code block."

    # Placeholder for code blocks when read_code_blocks is False
    # Set to empty string to completely remove code blocks
    code_block_placeholder: str = "Code omitted."

    # Prefix for images when read_images is True
    image_prefix: str = "Image:"


# Default options instance
DEFAULT_OPTIONS = MarkdownToSpeechOptions()


def markdown_to_speech(
    text: str, options: Optional[MarkdownToSpeechOptions] = None
) -> str:
    """
    Convert markdown text to natural speech-friendly text.

    This function uses markdown-it-py to parse markdown into HTML,
    then uses BeautifulSoup to extract clean text.

    Args:
        text: Markdown-formatted text
        options: Optional configuration for conversion behavior

    Returns:
        Plain text suitable for TTS

    Examples:
        >>> markdown_to_speech("This is **bold** text")
        'This is bold text'

        >>> markdown_to_speech("Click [here](https://example.com)")
        'Click here'
    """
    if not text:
        return ""

    # Truncate input to prevent resource exhaustion
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]

    opts = options or DEFAULT_OPTIONS

    # Step 1: Handle SAM-specific citations BEFORE markdown parsing
    # (markdown-it doesn't recognize these custom formats)
    result = _handle_sam_citations(text, opts)

    # Step 2: Handle code blocks specially (before markdown parsing)
    # We need to do this first because we want to control how they're rendered
    result = _handle_code_blocks_pre(result, opts)

    # Step 3: Handle ordered lists to preserve numbers (before markdown parsing)
    # markdown-it renders <ol><li> which loses the original numbers
    result = _handle_ordered_lists_pre(result)

    # Step 4: Convert markdown to HTML using markdown-it-py
    result = _markdown_to_html(result)

    # Step 5: Extract text from HTML using BeautifulSoup
    result = _html_to_text(result, opts)

    # Step 6: Handle bare URLs that might have been missed
    result = _handle_bare_urls(result)

    # Step 7: Normalize whitespace for natural speech
    result = _normalize_whitespace(result)

    return result.strip()


def _markdown_to_html(text: str) -> str:
    """Convert markdown to HTML using markdown-it-py.
    """
    from markdown_it import MarkdownIt

    # Create parser with commonmark preset 
    # and enable tables and strikethrough for better markdown support
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    return md.render(text)


def _html_to_text(html_content: str, opts: MarkdownToSpeechOptions) -> str:
    """Extract plain text from HTML using BeautifulSoup.

    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")

    # Handle images - either announce them or remove them
    for img in soup.find_all("img"):
        alt_text = img.get("alt", "").strip()
        if opts.read_images and alt_text:
            img.replace_with(f" {opts.image_prefix} {alt_text}. ")
        else:
            img.decompose()

    # Handle code blocks
    for code in soup.find_all("pre"):
        if opts.read_code_blocks:
            code.replace_with(f" {opts.code_block_prefix} ")
        else:
            code.decompose()

    # Add periods after headers for natural pauses
    if opts.add_header_pauses:
        for header in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            header_text = header.get_text().strip()
            header.replace_with(f"{header_text}. ")

    # Get text content
    text = soup.get_text(separator=" ")

    # Decode any remaining HTML entities
    text = html.unescape(text)

    return text


def _handle_code_blocks_pre(text: str, opts: MarkdownToSpeechOptions) -> str:
    """
    Pre-process code blocks before markdown parsing.
    This ensures we have control over how they're handled.
    """
    if opts.read_code_blocks:
        replacement = f" {opts.code_block_prefix} "
    elif opts.code_block_placeholder:
        replacement = f" {opts.code_block_placeholder} "
    else:
        replacement = " "
    result = []
    i = 0
    text_len = len(text)

    while i < text_len:
        # Look for opening ```
        if text[i : i + 3] == "```":
            # Find the closing ```
            # Skip past the opening ``` and any language identifier
            start = i + 3
            # Skip language identifier (word characters until newline or space)
            while start < text_len and text[start] not in "\n \t`":
                start += 1
            # Find closing ```
            close_pos = text.find("```", start)
            if close_pos != -1:
                # Found a complete code block, replace it
                result.append(replacement)
                i = close_pos + 3
            else:
                # No closing ```, treat as regular text
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1

    return "".join(result)


def _handle_ordered_lists_pre(text: str) -> str:
    """
    Pre-process ordered lists to preserve numbers before markdown parsing.

    markdown-it renders ordered lists as <ol><li> which loses the original
    numbers. This function converts "1. Item" to "1, Item" so the numbers
    are preserved in the final text.
    """
    lines = text.split("\n")
    result_lines = []
    for line in lines:
        # Match ordered list items: "1. Item" or "  1. Item" (with leading spaces)
        # Using explicit character classes to avoid regex quantifier issues
        stripped = line.lstrip(" \t")
        if stripped and len(stripped) > 2:
            # Check if line starts with digit(s) followed by ". "
            dot_pos = stripped.find(". ")
            if dot_pos > 0 and dot_pos <= 10:  # Reasonable limit for list numbers
                prefix = stripped[:dot_pos]
                if prefix.isdigit():
                    # Replace "N. " with "N, " to preserve the number
                    leading_space = line[: len(line) - len(stripped)]
                    rest = stripped[dot_pos + 2 :]
                    result_lines.append(f"{leading_space}{prefix}, {rest}")
                    continue
        result_lines.append(line)
    return "\n".join(result_lines)


def _handle_sam_citations(text: str, opts: MarkdownToSpeechOptions) -> str:
    """
    Handle SAM-specific citation formats that markdown parsers don't recognize.

    Formats handled:
    - Simple: [1], [2], etc.
    - SAM cite format: [[cite:search0]], [[cite:research0]], [[cite:file0]], [[cite:ref0]]
    - Web search format: [[cite:s1r1]], [[cite:s2r3]] (s=search turn, r=result index)
    - Multi-citations: [[cite:search0, search1, search2]]
    - Single bracket variants: [cite:search0]
    """
    if not opts.read_citations:
        # Remove all citation formats entirely
        text = re.sub(r"\[?\[cite:[^\]]+\]\]?", "", text)
        text = re.sub(r"\[(\d+)\]", "", text)
        return text

    # Handle web search format: [[cite:s1r1]], [[cite:s2r3]]
    def replace_web_search_citation(match):
        search_turn = match.group(1)
        result_index = match.group(2)
        return f", search {search_turn} result {result_index},"

    text = re.sub(
        r"\[?\[cite:s(\d+)r(\d+)\]\]?", replace_web_search_citation, text
    )

    # Handle SAM-style multi-citations
    def replace_multi_citation(match):
        content = match.group(1)
        individual_pattern = r"(?:cite:)?(file|ref|search|research)?(\d+)"
        citations = re.findall(individual_pattern, content)
        if not citations:
            return ""

        spoken_parts = []
        for cite_type, num in citations:
            cite_type = cite_type or "search"
            display_num = str(int(num) + 1)
            if cite_type == "research":
                spoken_parts.append(f"research source {display_num}")
            elif cite_type == "search":
                spoken_parts.append(f"source {display_num}")
            elif cite_type == "file":
                spoken_parts.append(f"file {display_num}")
            elif cite_type == "ref":
                spoken_parts.append(f"reference {display_num}")
            else:
                spoken_parts.append(f"source {display_num}")

        if len(spoken_parts) == 1:
            return f", {spoken_parts[0]},"
        elif len(spoken_parts) == 2:
            return f", {spoken_parts[0]} and {spoken_parts[1]},"
        else:
            return f', {", ".join(spoken_parts[:-1])}, and {spoken_parts[-1]},'

    multi_cite_pattern = r"\[?\[cite:((?:(?:file|ref|search|research)?\d+)(?:\s*,\s*(?:cite:)?(?:file|ref|search|research)?\d+)+)\]\]?"
    text = re.sub(multi_cite_pattern, replace_multi_citation, text)

    # Handle SAM-style single citations
    def replace_sam_citation(match):
        cite_type = match.group(1) or "search"
        num = match.group(2)
        display_num = str(int(num) + 1)

        if cite_type == "research":
            spoken = f"research source {display_num}"
        elif cite_type == "search":
            spoken = f"source {display_num}"
        elif cite_type == "file":
            spoken = f"file {display_num}"
        elif cite_type == "ref":
            spoken = f"reference {display_num}"
        else:
            spoken = f"source {display_num}"

        return f", {spoken},"

    sam_cite_pattern = r"\[?\[cite:(?:(file|ref|search|research))?(\d+)\]\]?"
    text = re.sub(sam_cite_pattern, replace_sam_citation, text)

    # Handle simple citations [1], [2], etc.
    if opts.citation_format:

        def replace_simple_citation(match):
            num = match.group(1)
            spoken = opts.citation_format.replace("{n}", num)
            return f", {spoken},"

        text = re.sub(r"\[(\d+)\]", replace_simple_citation, text)
    else:
        text = re.sub(r"\[(\d+)\]", "", text)

    return text


def _handle_bare_urls(text: str) -> str:
    """Replace bare URLs with 'link' for natural speech."""
    url_pattern = r"(?<!\()\bhttps?://[^\s<>\[\]()]+\b"
    return re.sub(url_pattern, "link", text)


def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace for natural speech.

    """
    # Replace newlines/carriage returns with single space
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")

    # Replace multiple spaces with single space using split/join
    # This is more efficient than regex for this simple case
    text = " ".join(text.split())

    # Clean up punctuation spacing - remove spaces before punctuation
    # Using character-by-character replacement to avoid regex quantifiers
    for punct in ".,!?;:":
        text = text.replace(f" {punct}", punct)

    # Remove duplicate commas from citation handling
    while ",," in text or ", ," in text:
        text = text.replace(",,", ",").replace(", ,", ",")

    return text
