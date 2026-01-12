"""
Example tools demonstrating streaming status updates from a Lambda function.

These tools send periodic status updates during processing, which are streamed
back to SAM via NDJSON over the Lambda Function URL connection.
"""

import asyncio
import json
from collections import Counter
from agent_tools import ToolResult, ToolContextBase, Artifact, DataObject


async def slow_process(
    message: str,
    steps: int,
    ctx: ToolContextBase,
) -> ToolResult:
    """
    Process a message with streaming status updates.

    This tool simulates a long-running process that sends status updates
    at each step. Use it to test streaming functionality.

    Args:
        message: The message to process
        steps: Number of processing steps (each takes ~1 second)
        ctx: Tool context for sending status updates

    Returns:
        ToolResult with the processed message and step count
    """
    ctx.send_status(f"Starting to process: {message}")

    for i in range(steps):
        await asyncio.sleep(1)  # Simulate work
        ctx.send_status(f"Step {i + 1}/{steps} complete...")

    return ToolResult.ok(
        message=f"Processed '{message}' in {steps} steps",
        data={"steps_completed": steps, "original_message": message},
    )


async def analyze_document(
    document: Artifact,
    ctx: ToolContextBase,
) -> ToolResult:
    """
    Analyze a text document with streaming progress updates.

    This tool demonstrates artifact input and output with streaming status
    updates. It performs a comprehensive analysis of the document content
    and returns the results as a new artifact.

    Args:
        document: The text document to analyze (artifact will be pre-loaded)
        ctx: Tool context for sending status updates

    Returns:
        ToolResult with analysis summary and a detailed report artifact
    """
    ctx.send_status(f"Starting analysis of '{document.filename}'...")
    await asyncio.sleep(0.5)

    # Get the document content
    try:
        content = document.as_text()
    except Exception as e:
        return ToolResult.error(f"Failed to read document: {e}")

    ctx.send_status("Reading document content...")
    await asyncio.sleep(0.5)

    # Step 1: Basic statistics
    ctx.send_status("Calculating basic statistics...")
    await asyncio.sleep(1)

    lines = content.split('\n')
    line_count = len(lines)
    char_count = len(content)
    char_count_no_spaces = len(content.replace(' ', '').replace('\n', ''))

    # Step 2: Word analysis
    ctx.send_status("Analyzing words...")
    await asyncio.sleep(1)

    words = content.split()
    word_count = len(words)
    unique_words = set(word.lower().strip('.,!?;:()[]{}"\'-') for word in words)
    unique_word_count = len(unique_words)
    avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0

    # Step 3: Frequency analysis
    ctx.send_status("Performing frequency analysis...")
    await asyncio.sleep(1)

    word_freq = Counter(
        word.lower().strip('.,!?;:()[]{}"\'-')
        for word in words
        if word.strip('.,!?;:()[]{}"\'-')
    )
    top_words = word_freq.most_common(10)

    # Step 4: Sentence analysis
    ctx.send_status("Analyzing sentence structure...")
    await asyncio.sleep(1)

    # Simple sentence detection
    sentences = [s.strip() for s in content.replace('!', '.').replace('?', '.').split('.') if s.strip()]
    sentence_count = len(sentences)
    avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

    # Step 5: Generate report
    ctx.send_status("Generating analysis report...")
    await asyncio.sleep(0.5)

    report = f"""Document Analysis Report
========================
Source: {document.filename} (v{document.version})
MIME Type: {document.mime_type}

BASIC STATISTICS
----------------
- Characters (total): {char_count:,}
- Characters (no spaces): {char_count_no_spaces:,}
- Lines: {line_count:,}
- Words: {word_count:,}
- Sentences: {sentence_count:,}

WORD ANALYSIS
-------------
- Unique words: {unique_word_count:,}
- Vocabulary richness: {(unique_word_count/word_count*100):.1f}% (unique/total)
- Average word length: {avg_word_length:.1f} characters

TOP 10 MOST FREQUENT WORDS
--------------------------
"""
    for i, (word, count) in enumerate(top_words, 1):
        report += f"{i:2}. '{word}' - {count} occurrences\n"

    report += f"""
READABILITY METRICS
-------------------
- Average sentence length: {avg_sentence_length:.1f} words
- Estimated reading time: {word_count // 200} min {(word_count % 200) // 4} sec (at 200 WPM)
"""

    ctx.send_status("Analysis complete!")

    # Create the report as a data object (artifact)
    report_artifact = DataObject(
        data=report,
        mime_type="text/plain",
        filename=f"{document.filename}_analysis.txt",
    )

    return ToolResult.ok(
        message=f"Analysis complete for '{document.filename}'",
        data={
            "source_file": document.filename,
            "word_count": word_count,
            "unique_words": unique_word_count,
            "line_count": line_count,
            "sentence_count": sentence_count,
            "top_words": [{"word": w, "count": c} for w, c in top_words[:5]],
        },
        data_objects=[report_artifact],
    )
