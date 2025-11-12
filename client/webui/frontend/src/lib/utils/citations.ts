/**
 * Citation utilities for parsing and handling RAG source citations
 * Uses [[cite:type0]] pattern that LLMs can reliably reproduce
 * Also supports [[cite:research0]] for deep research citations
 */

import type { RAGSource, RAGSearchResult } from '@/lib/types/fe';

// Citation marker pattern: [[cite:file0]], [[cite:ref0]], [[cite:research0]], etc.
// Also matches single bracket [cite:xxx] in case LLM uses wrong format
export const CITATION_PATTERN = /\[?\[cite:(file|ref|search|research)(\d+)\]\]?/g;
export const CLEANUP_REGEX = /\[?\[cite:[^\]]+\]\]?/g;

export interface Citation {
  marker: string;
  type: 'file' | 'ref' | 'search' | 'research';
  sourceId: number;
  position: number;
  source?: RAGSource;
}

// Re-export for convenience
export type { RAGSource, RAGSearchResult as RAGMetadata };

/**
 * Parse citation markers from text and match them to RAG metadata
 */
export function parseCitations(
  text: string,
  ragMetadata?: RAGSearchResult
): Citation[] {
  const citations: Citation[] = [];
  let match;
  
  // Reset regex state
  CITATION_PATTERN.lastIndex = 0;
  
  while ((match = CITATION_PATTERN.exec(text)) !== null) {
    const [fullMatch, type, sourceId] = match;
    const citation: Citation = {
      marker: fullMatch,
      type: type as 'file' | 'ref' | 'search' | 'research',
      sourceId: parseInt(sourceId, 10),
      position: match.index,
    };
    
    // Match to source metadata if available
    if (ragMetadata?.sources) {
      const citationId = `${type}${sourceId}`;
      citation.source = ragMetadata.sources.find(
        (s: RAGSource) => s.citation_id === citationId
      );
      
      // Debug logging to help troubleshoot citation matching
      if (!citation.source && ragMetadata.sources.length > 0) {
        console.log(`Citation ${citationId} not found in sources:`, ragMetadata.sources.map(s => s.citation_id));
      }
    }
    
    citations.push(citation);
  }
  
  return citations;
}

/**
 * Remove citation markers from text (for display without citations)
 */
export function removeCitationMarkers(text: string): string {
  return text.replace(CITATION_PATTERN, '');
}

/**
 * Split text into segments with citations
 * Returns array of {text, citation} objects
 */
export function splitTextWithCitations(
  text: string,
  citations: Citation[]
): Array<{ text: string; citation?: Citation }> {
  if (citations.length === 0) {
    return [{ text }];
  }
  
  const segments: Array<{ text: string; citation?: Citation }> = [];
  let lastIndex = 0;
  
  // Sort citations by position
  const sortedCitations = [...citations].sort((a, b) => a.position - b.position);
  
  for (const citation of sortedCitations) {
    // Add text before citation
    if (citation.position > lastIndex) {
      segments.push({
        text: text.substring(lastIndex, citation.position)
      });
    }
    
    // Add citation marker (will be replaced with component)
    segments.push({
      text: citation.marker,
      citation
    });
    
    lastIndex = citation.position + citation.marker.length;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    segments.push({
      text: text.substring(lastIndex)
    });
  }
  
  return segments;
}

/**
 * Get citation display number (1-indexed)
 */
export function getCitationNumber(citation: Citation): number {
  return citation.sourceId + 1;
}

/**
 * Get citation tooltip text
 */
export function getCitationTooltip(citation: Citation): string {
  // For web search citations, show the URL and title
  const isWebSearch = citation.source?.metadata?.type === 'web_search' || citation.type === 'search';
  
  if (isWebSearch && citation.source?.source_url) {
    const title = citation.source.metadata?.title || citation.source.filename;
    if (title && title !== citation.source.source_url) {
      return `${title}\n${citation.source.source_url}`;
    }
    return citation.source.source_url;
  }
  
  if (!citation.source) {
    return `Source ${getCitationNumber(citation)}`;
  }
  
  const score = (citation.source.relevance_score * 100).toFixed(1);
  return `${citation.source.filename} (${score}% relevance)`;
}

/**
 * Get citation link URL (for kb_search with source URLs)
 */
export function getCitationLink(citation: Citation): string | undefined {
  return citation.source?.source_url;
}