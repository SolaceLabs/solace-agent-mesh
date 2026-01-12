"""
Markdown to Speech Preprocessor
Converts markdown-formatted text to natural, speakable text suitable for
Text-to-Speech (TTS) engines. 
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
    
    # Prefix for images when read_images is True
    image_prefix: str = "Image:"


# Default options instance
DEFAULT_OPTIONS = MarkdownToSpeechOptions()

def markdown_to_speech(
    text: str,
    options: Optional[MarkdownToSpeechOptions] = None
) -> str:
    """
    Convert markdown text to natural speech-friendly text.
    
    This function removes markdown syntax while preserving the semantic
    meaning of the content, making it suitable for TTS engines.
    
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
    result = text
    
    # Step 1: Handle code blocks (``` ... ```)
    # Must be done before inline code to avoid conflicts
    result = _handle_code_blocks(result, opts)
    
    # Step 2: Handle inline code (`code`)
    result = _handle_inline_code(result)
    
    # Step 3: Handle images ![alt](url)
    result = _handle_images(result, opts)
    
    # Step 4: Handle links [text](url)
    result = _handle_links(result)
    
    # Step 5: Handle reference-style links [text][ref] and [ref]: url
    result = _handle_reference_links(result)
    
    # Step 6: Handle bold and italic
    result = _handle_emphasis(result)
    
    # Step 7: Handle headers
    result = _handle_headers(result, opts)
    
    # Step 8: Handle blockquotes
    result = _handle_blockquotes(result)
    
    # Step 9: Handle horizontal rules
    result = _handle_horizontal_rules(result)
    
    # Step 10: Handle lists (unordered and ordered)
    result = _handle_lists(result)
    
    # Step 11: Handle citations [1], [2], etc.
    result = _handle_citations(result, opts)
    
    # Step 12: Handle tables (basic - just extract text)
    result = _handle_tables(result)
    
    # Step 13: Strip HTML tags
    result = _strip_html_tags(result)
    
    # Step 14: Decode HTML entities
    result = _decode_html_entities(result)
    
    # Step 15: Handle bare URLs
    result = _handle_bare_urls(result)
    
    # Step 16: Normalize whitespace
    result = _normalize_whitespace(result)
    
    return result.strip()


def _handle_code_blocks(text: str, opts: MarkdownToSpeechOptions) -> str:
    """Remove or replace fenced code blocks."""
    # Match ```language\ncode\n``` or ```\ncode\n```
    pattern = r'```[\w]*\n?[\s\S]*?```'
    
    if opts.read_code_blocks:
        # Replace with announcement
        return re.sub(pattern, f' {opts.code_block_prefix} ', text)
    else:
        # Remove entirely
        return re.sub(pattern, ' ', text)


def _handle_inline_code(text: str) -> str:
    """Remove backticks from inline code, keeping the content."""
    # Match `code` but not inside code blocks (already handled)
    return re.sub(r'`([^`]+)`', r'\1', text)


def _handle_images(text: str, opts: MarkdownToSpeechOptions) -> str:
    """Handle image markdown ![alt](url)."""
    if opts.read_images:
        # Replace with "Image: alt text"
        def replace_image(match):
            alt_text = match.group(1).strip()
            if alt_text:
                return f' {opts.image_prefix} {alt_text}. '
            return ' '
        return re.sub(r'!\[([^\]]*)\]\([^)]+\)', replace_image, text)
    else:
        # Remove entirely
        return re.sub(r'!\[([^\]]*)\]\([^)]+\)', ' ', text)


def _handle_links(text: str) -> str:
    """Extract link text from [text](url) format."""
    # Keep the link text, remove the URL
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)


def _handle_reference_links(text: str) -> str:
    """Handle reference-style links [text][ref] and remove [ref]: url definitions."""
    # Remove reference definitions [ref]: url
    text = re.sub(r'^\s*\[[^\]]+\]:\s*\S+.*$', '', text, flags=re.MULTILINE)
    
    # Convert [text][ref] to just text
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    
    return text


def _handle_emphasis(text: str) -> str:
    """Remove bold and italic markers."""
    # Bold: **text** or __text__
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    
    # Italic: *text* or _text_ (but not inside words like snake_case)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', text)
    
    # Strikethrough: ~~text~~
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    return text


def _handle_headers(text: str, opts: MarkdownToSpeechOptions) -> str:
    """Remove header markers, optionally add pause."""
    # Match # Header, ## Header, etc.
    def replace_header(match):
        header_text = match.group(2).strip()
        if opts.add_header_pauses:
            return f'{header_text}. '
        return f'{header_text} '
    
    # Handle headers at start of line
    text = re.sub(r'^(#{1,6})\s+(.+)$', replace_header, text, flags=re.MULTILINE)
    
    # Handle setext-style headers (underlined with === or ---)
    text = re.sub(r'^(.+)\n[=]+\s*$', r'\1. ', text, flags=re.MULTILINE)
    text = re.sub(r'^(.+)\n[-]+\s*$', r'\1. ', text, flags=re.MULTILINE)
    
    return text


def _handle_blockquotes(text: str) -> str:
    """Remove blockquote markers."""
    # Remove > at the start of lines
    return re.sub(r'^>\s*', '', text, flags=re.MULTILINE)


def _handle_horizontal_rules(text: str) -> str:
    """Remove horizontal rules."""
    # Match ---, ***, ___ (3 or more)
    return re.sub(r'^[-*_]{3,}\s*$', ' ', text, flags=re.MULTILINE)


def _handle_lists(text: str) -> str:
    """Clean up list markers for natural reading."""
    # Unordered lists: -, *, +
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    
    # Ordered lists: 1., 2., etc. - keep the number for context
    # "1. First item" becomes "1, First item" for natural reading
    text = re.sub(r'^[\s]*(\d+)\.\s+', r'\1, ', text, flags=re.MULTILINE)
    
    return text


def _handle_citations(text: str, opts: MarkdownToSpeechOptions) -> str:
    """
    Handle citation references in various formats:
    - Simple: [1], [2], etc.
    - SAM cite format: [[cite:search0]], [[cite:research0]], [[cite:file0]], [[cite:ref0]]
    - Web search format: [[cite:s1r1]], [[cite:s2r3]] (s=search turn, r=result index)
    - Multi-citations: [[cite:search0, search1, search2]] or [[cite:research0, cite:research1]]
    - Single bracket variants: [cite:search0]
    """
    if not opts.read_citations:
        # Remove all citation formats entirely
        # Multi-citation pattern first (to avoid partial matches)
        text = re.sub(r'\[?\[cite:[^\]]+\]\]?', '', text)
        # Simple citations
        text = re.sub(r'\[(\d+)\]', '', text)
        return text
    
    # Handle web search format: [[cite:s1r1]], [[cite:s2r3]] (s=search turn, r=result index)
    def replace_web_search_citation(match):
        search_turn = match.group(1)
        result_index = match.group(2)
        # Convert to 1-indexed for natural speech
        search_num = str(int(search_turn))  
        result_num = str(int(result_index)) 
        return f', search {search_num} result {result_num},'
    
    # Web search citation pattern: [[cite:s1r1]] or [cite:s1r1]
    web_search_pattern = r'\[?\[cite:s(\d+)r(\d+)\]\]?'
    text = re.sub(web_search_pattern, replace_web_search_citation, text)
    
    # Handle SAM-style multi-citations: [[cite:search0, search1]] or [[cite:research0, cite:research1]]
    def replace_multi_citation(match):
        content = match.group(1)
        # Extract individual citation numbers (handles both type+num and s#r# formats)
        individual_pattern = r'(?:cite:)?(file|ref|search|research)?(\d+)'
        citations = re.findall(individual_pattern, content)
        if not citations:
            return ''
        
        # Build spoken text for each citation
        spoken_parts = []
        for cite_type, num in citations:
            cite_type = cite_type or 'search'  # Default to search if no type
            # Convert 0-indexed to 1-indexed for natural speech
            display_num = str(int(num) + 1)
            if cite_type == 'research':
                spoken_parts.append(f'research source {display_num}')
            elif cite_type == 'search':
                spoken_parts.append(f'source {display_num}')
            elif cite_type == 'file':
                spoken_parts.append(f'file {display_num}')
            elif cite_type == 'ref':
                spoken_parts.append(f'reference {display_num}')
            else:
                spoken_parts.append(f'source {display_num}')
        
        if len(spoken_parts) == 1:
            return f', {spoken_parts[0]},'
        elif len(spoken_parts) == 2:
            return f', {spoken_parts[0]} and {spoken_parts[1]},'
        else:
            # Join with commas and "and" for last item
            return f', {", ".join(spoken_parts[:-1])}, and {spoken_parts[-1]},'
    
    # Multi-citation pattern: [[cite:search0, search1, search2]] or [[cite:research0, cite:research1]]
    multi_cite_pattern = r'\[?\[cite:((?:(?:file|ref|search|research)?\d+)(?:\s*,\s*(?:cite:)?(?:file|ref|search|research)?\d+)+)\]\]?'
    text = re.sub(multi_cite_pattern, replace_multi_citation, text)
    
    # Handle SAM-style single citations: [[cite:search0]], [[cite:research0]], etc.
    def replace_sam_citation(match):
        cite_type = match.group(1) or 'search'  # Default to search if no type
        num = match.group(2)
        # Convert 0-indexed to 1-indexed for natural speech
        display_num = str(int(num) + 1)
        
        if cite_type == 'research':
            spoken = f'research source {display_num}'
        elif cite_type == 'search':
            spoken = f'source {display_num}'
        elif cite_type == 'file':
            spoken = f'file {display_num}'
        elif cite_type == 'ref':
            spoken = f'reference {display_num}'
        else:
            spoken = f'source {display_num}'
        
        return f', {spoken},'
    
    # Single SAM citation pattern: [[cite:type0]] or [cite:type0] or [[cite:0]]
    sam_cite_pattern = r'\[?\[cite:(?:(file|ref|search|research))?(\d+)\]\]?'
    text = re.sub(sam_cite_pattern, replace_sam_citation, text)
    
    # Handle simple citations [1], [2], etc. (traditional format)
    if opts.citation_format:
        def replace_simple_citation(match):
            num = match.group(1)
            spoken = opts.citation_format.replace('{n}', num)
            return f', {spoken},'
        text = re.sub(r'\[(\d+)\]', replace_simple_citation, text)
    else:
        text = re.sub(r'\[(\d+)\]', '', text)
    
    return text


def _handle_tables(text: str) -> str:
    """Extract text from markdown tables."""
    lines = text.split('\n')
    result_lines = []
    
    for line in lines:
        # Skip separator lines (|---|---|)
        if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
            continue
        
        # Extract cell content from table rows
        if '|' in line:
            # Remove leading/trailing pipes and split
            cells = line.strip().strip('|').split('|')
            # Join cell contents with spaces
            cell_text = ' '.join(cell.strip() for cell in cells if cell.strip())
            result_lines.append(cell_text)
        else:
            result_lines.append(line)
    
    return '\n'.join(result_lines)


def _strip_html_tags(text: str) -> str:
    """Remove HTML tags from text."""
    # Remove HTML comments
    text = re.sub(r'<!--[\s\S]*?-->', '', text)
    
    # Remove HTML tags but keep content
    text = re.sub(r'<[^>]+>', '', text)
    
    return text


def _decode_html_entities(text: str) -> str:
    """Decode HTML entities like &amp; to &."""
    return html.unescape(text)


def _handle_bare_urls(text: str) -> str:
    """Remove or simplify bare URLs."""
    # Match URLs that aren't part of markdown links
    # Replace with "link" to indicate there was a URL
    url_pattern = r'(?<!\()\b(https?://[^\s<>\[\]()]+)'
    return re.sub(url_pattern, 'link', text)


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for natural speech."""
    # Replace multiple newlines with single space
    text = re.sub(r'\n{2,}', ' ', text)
    
    # Replace single newlines with space
    text = re.sub(r'\n', ' ', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    
    # Clean up punctuation spacing
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    
    # Remove spaces before commas that we added for citations
    text = re.sub(r'\s*,\s*,', ',', text)
    
    return text
