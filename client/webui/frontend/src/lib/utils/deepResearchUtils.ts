/**
 * Utility functions for deep research report processing
 */

/**
 * Strips the References and Research Methodology sections from a deep research report.
 * These sections are typically at the end of the report and start with "## References"
 * and "## Research Methodology" headings.
 *
 * @param markdownContent - The full markdown content of the deep research report
 * @returns The markdown content without the References and Methodology sections
 */
export function stripReportMetadataSections(markdownContent: string): string {
    if (!markdownContent) {
        return markdownContent;
    }

    // Find the position of "## References" section (case-insensitive)
    // This section and everything after it should be removed
    const referencesPattern = /\n---\n\n## References\b/i;
    const referencesMatch = markdownContent.match(referencesPattern);

    if (referencesMatch && referencesMatch.index !== undefined) {
        // Remove everything from the "---" before References to the end
        return markdownContent.substring(0, referencesMatch.index).trim();
    }

    // If no "---" separator, try to find just "## References"
    const simpleReferencesPattern = /\n## References\b/i;
    const simpleReferencesMatch = markdownContent.match(simpleReferencesPattern);

    if (simpleReferencesMatch && simpleReferencesMatch.index !== undefined) {
        return markdownContent.substring(0, simpleReferencesMatch.index).trim();
    }

    // Also check for "## Research Methodology" in case References is missing
    const methodologyPattern = /\n## Research Methodology\b/i;
    const methodologyMatch = markdownContent.match(methodologyPattern);

    if (methodologyMatch && methodologyMatch.index !== undefined) {
        return markdownContent.substring(0, methodologyMatch.index).trim();
    }

    // No sections to strip, return original content
    return markdownContent;
}

/**
 * Checks if a filename looks like a deep research report artifact
 *
 * @param filename - The filename to check
 * @returns True if the filename matches the deep research report pattern
 */
export function isDeepResearchReportFilename(filename: string): boolean {
    if (!filename) {
        return false;
    }

    // Deep research reports are saved with "_report.md" suffix
    // e.g., "what_is_the_latest_news_on_ai_report.md"
    return filename.toLowerCase().endsWith("_report.md");
}
