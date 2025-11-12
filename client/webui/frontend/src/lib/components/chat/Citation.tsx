/**
 * Citation component for displaying clickable source citations
 */
import React, { Fragment } from 'react';
import type { Citation as CitationType } from '@/lib/utils/citations';
import { getCitationTooltip, splitTextWithCitations } from '@/lib/utils/citations';
import { MarkdownHTMLConverter } from '@/lib/components';

interface CitationProps {
  citation: CitationType;
  onClick?: (citation: CitationType) => void;
  maxLength?: number;
}

/**
 * Truncate text to fit within maxLength, adding ellipsis if needed
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength - 3) + '...';
}

/**
 * Extract clean filename from file_id by removing session prefix if present
 * Same logic as RAGInfoPanel, but only applies if the filename has the session pattern
 */
function extractFilename(filename: string): string {
  // Check if this looks like a session-prefixed filename
  const hasSessionPrefix = filename.includes('web-session-') || filename.startsWith('sam_dev_user_');
  
  // If it doesn't have a session prefix, return as-is
  if (!hasSessionPrefix) {
    return filename;
  }
  
  // The pattern is: sam_dev_user_web-session-{uuid}_{actual_filename}_v{version}.pdf
  // We need to extract just the {actual_filename}.pdf part
  
  // First, remove the .pdf extension at the very end (added by backend)
  let cleaned = filename.replace(/\.pdf$/, '');
  
  // Remove the version suffix (_v0, _v1, etc.)
  cleaned = cleaned.replace(/_v\d+$/, '');
  
  // Now we have: sam_dev_user_web-session-{uuid}_{actual_filename}
  // Find the pattern "web-session-{uuid}_" and remove everything before and including it
  const sessionPattern = /^.*web-session-[a-f0-9-]+_/;
  cleaned = cleaned.replace(sessionPattern, '');
  
  // Add back the .pdf extension
  return cleaned + '.pdf';
}

/**
 * Get display text for citation (filename or URL)
 */
function getCitationDisplayText(citation: CitationType, maxLength: number = 30): string {
  // For web search citations, try to extract domain name even without full source data
  const isWebSearch = citation.source?.metadata?.type === 'web_search' || citation.type === 'search';
  
  if (isWebSearch && citation.source?.source_url) {
    try {
      const url = new URL(citation.source.source_url);
      const domain = url.hostname.replace(/^www\./, '');
      return truncateText(domain, maxLength);
    } catch {
      // If URL parsing fails, fall through to other methods
    }
  }
  
  // Check if source has a URL in metadata
  if (citation.source?.metadata?.link) {
    try {
      const url = new URL(citation.source.metadata.link);
      const domain = url.hostname.replace(/^www\./, '');
      return truncateText(domain, maxLength);
    } catch {
      // If URL parsing fails, continue
    }
  }
  
  // If no source data but it's a search citation, try to infer from citation type
  if (!citation.source && citation.type === 'search') {
    // For search citations without source data, show a more descriptive label
    return `Web Source ${citation.sourceId + 1}`;
  }
  
  if (!citation.source) {
    return `Source ${citation.sourceId + 1}`;
  }
  
  // The filename field contains the original filename (not the temp path)
  // The source_url field contains the temp path (not useful for display)
  if (citation.source.filename) {
    // For KB search, filename already contains the original name
    // For file search, it might have session prefix that needs extraction
    const hasSessionPrefix = citation.source.filename.includes('web-session-') ||
                            citation.source.filename.startsWith('sam_dev_user_');
    
    const displayName = hasSessionPrefix
      ? extractFilename(citation.source.filename)
      : citation.source.filename;
    
    return truncateText(displayName, maxLength);
  }
  
  // Fallback to source URL if no filename
  if (citation.source.source_url) {
    // Try to extract domain name or filename from URL
    try {
      const url = new URL(citation.source.source_url);
      const domain = url.hostname.replace(/^www\./, '');
      return truncateText(domain, maxLength);
    } catch {
      // If URL parsing fails, try to extract filename
      const filename = citation.source.source_url.split('/').pop() || citation.source.source_url;
      return truncateText(filename, maxLength);
    }
  }
  
  return `Source ${citation.sourceId + 1}`;
}

export function Citation({ citation, onClick, maxLength = 30 }: CitationProps) {
  const displayText = getCitationDisplayText(citation, maxLength);
  const tooltip = getCitationTooltip(citation);
  
  // Check if this is a web search citation
  const isWebSearch = citation.source?.metadata?.type === 'web_search';
  const webSearchUrl = isWebSearch ? citation.source?.source_url : null;
  
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    // For web search citations, open the URL directly
    if (isWebSearch && webSearchUrl) {
      window.open(webSearchUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    
    // For RAG citations, use onClick handler (to open RAG panel)
    if (onClick) {
      onClick(citation);
    }
  };
  
  return (
    <button
      onClick={handleClick}
      className="citation-badge inline-flex items-center px-1.5 py-0.5 mx-0.5
                 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600
                 text-gray-800 dark:text-white text-[11px] font-normal
                 rounded-sm
                 transition-colors duration-150 cursor-pointer
                 align-baseline whitespace-nowrap"
      title={tooltip}
      aria-label={`Citation: ${tooltip}`}
      type="button"
    >
      <span className="truncate max-w-[200px]">{displayText}</span>
    </button>
  );
}

/**
 * Component to render text with embedded citations
 */
interface TextWithCitationsProps {
  text: string;
  citations: CitationType[];
  onCitationClick?: (citation: CitationType) => void;
}

export function TextWithCitations({ text, citations, onCitationClick }: TextWithCitationsProps) {
  if (citations.length === 0) {
    return <MarkdownHTMLConverter>{text}</MarkdownHTMLConverter>;
  }
  
  const segments = splitTextWithCitations(text, citations);
  
  return (
    <span style={{ display: 'inline' }}>
      {segments.map((segment: { text: string; citation?: CitationType }, index: number) => {
        if (segment.citation) {
          return (
            <Citation
              key={`citation-${index}`}
              citation={segment.citation}
              onClick={onCitationClick}
            />
          );
        }
        // Render text segments as plain text to avoid block-level elements from MarkdownHTMLConverter
        return (
          <Fragment key={`text-${index}`}>{segment.text}</Fragment>
        );
      })}
    </span>
  );
}