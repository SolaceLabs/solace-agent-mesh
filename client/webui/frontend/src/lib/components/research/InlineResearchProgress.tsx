/**
 * Inline Research Progress Component
 *
 * Displays research stages building inline as they progress.
 * Each stage appears as a card that shows its status and details.
 */

import React, { useState } from 'react';
import { Search, Brain, FileText, Loader2, Globe, ChevronDown, ChevronUp } from 'lucide-react';
import type { RAGSearchResult } from '@/lib/types';

export interface ResearchProgressData {
  type: 'deep_research_progress';
  phase: 'planning' | 'searching' | 'analyzing' | 'writing';
  status_text: string;
  progress_percentage: number;
  current_iteration: number;
  total_iterations: number;
  sources_found: number;
  current_query: string;
  fetching_urls: Array<{url: string; title: string; favicon: string; source_type?: string}>;
  elapsed_seconds: number;
  max_runtime_seconds: number;
}

interface InlineResearchProgressProps {
  progress: ResearchProgressData;
  isComplete?: boolean;
  onClick?: () => void;
  ragData?: RAGSearchResult[];
}

interface StageInfo {
  phase: 'planning' | 'searching' | 'analyzing' | 'writing';
  icon: typeof Brain;
  label: string;
  description: string;
}

const stages: StageInfo[] = [
  {
    phase: 'planning',
    icon: Brain,
    label: 'Starting research',
    description: 'Planning research strategy',
  },
  {
    phase: 'searching',
    icon: Search,
    label: 'Exploring sources',
    description: 'Searching for relevant information',
  },
  {
    phase: 'analyzing',
    icon: Brain,
    label: 'Analyzing content',
    description: 'Processing and analyzing sources',
  },
  {
    phase: 'writing',
    icon: FileText,
    label: 'Generating report',
    description: 'Compiling final research',
  },
];

const getStageStatus = (
  stagePhase: string,
  currentPhase: string,
  isComplete: boolean
): 'pending' | 'active' | 'complete' => {
  const phaseOrder = ['planning', 'searching', 'analyzing', 'writing'];
  const stageIndex = phaseOrder.indexOf(stagePhase);
  const currentIndex = phaseOrder.indexOf(currentPhase);

  if (isComplete && stagePhase === 'writing') return 'complete';
  if (stageIndex < currentIndex) return 'complete';
  if (stageIndex === currentIndex) return 'active';
  return 'pending';
};

export const InlineResearchProgress: React.FC<InlineResearchProgressProps> = ({
  progress,
  isComplete = false,
  onClick,
  ragData,
}) => {
  // Use localStorage to persist accordion state across navigation
  const storageKey = `research-timeline-expanded`;
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(() => {
    const stored = localStorage.getItem(storageKey);
    return stored !== null ? stored === 'true' : true; // Default to true
  });
  
  const handleToggleTimeline = (e: React.MouseEvent) => {
    e.stopPropagation();
    const newState = !isTimelineExpanded;
    setIsTimelineExpanded(newState);
    localStorage.setItem(storageKey, String(newState));
  };
  
  // Build timeline events from ragData - interleave queries with their sources
  const timelineEvents = React.useMemo(() => {
    if (!ragData || ragData.length === 0) {
      console.log('[InlineResearchProgress] No ragData available');
      return [];
    }
    
    console.log('[InlineResearchProgress] Building timeline from ragData:', {
      ragDataCount: ragData.length,
      isComplete,
      firstSearchSample: ragData[0] ? {
        query: ragData[0].query,
        sourcesCount: ragData[0].sources?.length,
        metadata: (ragData[0] as any).metadata
      } : null
    });
    
    const events: Array<{
      type: 'search' | 'read';
      timestamp: string;
      content: string;
      url?: string;
      favicon?: string;
      title?: string;
    }> = [];
    
    // Check if we have query breakdown in metadata (new backend format)
    const firstSearch = ragData[0];
    const metadata = (firstSearch as any)?.metadata;
    const hasQueryBreakdown = metadata?.queries && Array.isArray(metadata.queries);
    
    // Check if we have multiple ragData entries (old format after refresh)
    const hasMultipleEntries = ragData.length > 1;
    
    console.log('[InlineResearchProgress] Query breakdown check:', {
      hasQueryBreakdown,
      hasMultipleEntries,
      ragDataLength: ragData.length,
      metadataKeys: metadata ? Object.keys(metadata) : [],
      queriesCount: hasQueryBreakdown ? metadata.queries.length : 0,
      fullMetadata: metadata,
      firstSearchStructure: {
        query: firstSearch.query,
        search_type: firstSearch.search_type,
        sourcesCount: firstSearch.sources?.length,
        hasMetadata: !!metadata
      }
    });
    
    if (hasQueryBreakdown && isComplete) {
      // NEW FORMAT: Single ragData entry with metadata.queries
      // New format: use query breakdown from backend to maintain order
      const queries = metadata.queries as Array<{
        query: string;
        timestamp: string;
        source_citation_ids: string[];
      }>;
      const allSources = firstSearch.sources;
      
      // Create a map of citation_id to source for quick lookup
      const sourceMap = new Map();
      allSources.forEach(source => {
        if (source.citation_id) {
          sourceMap.set(source.citation_id, source);
        }
      });
      
      queries.forEach((queryInfo: { query: string; timestamp: string; source_citation_ids: string[] }) => {
        // Add search event
        events.push({
          type: 'search',
          timestamp: queryInfo.timestamp,
          content: queryInfo.query
        });
        
        // Add read events for this query's fetched sources
        queryInfo.source_citation_ids.forEach((citId: string) => {
          const source = sourceMap.get(citId);
          if (source) {
            const wasFetched = source.metadata?.fetched === true ||
                              source.metadata?.fetch_status === 'success' ||
                              (source.content_preview && source.content_preview.includes('[Full Content Fetched]'));
            
            if (wasFetched && (source.url || source.title)) {
              events.push({
                type: 'read',
                timestamp: source.retrieved_at || queryInfo.timestamp,
                content: source.title || source.url || 'Unknown',
                url: source.url,
                favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ''),
                title: source.title
              });
            }
          }
        });
      });
    } else if (hasMultipleEntries && isComplete) {
      // OLD FORMAT AFTER REFRESH: Multiple ragData entries (one per query)
      // Reconstruct query→sources relationship from separate entries
      console.log('[InlineResearchProgress] Using multiple entries format (post-refresh)', {
        totalEntries: ragData.length,
        sampleEntries: ragData.slice(0, 3).map((s, i) => ({
          index: i,
          query: s.query,
          sourcesCount: s.sources?.length,
          timestamp: s.timestamp,
          firstSourceSample: s.sources?.[0] ? {
            title: s.sources[0].title,
            url: s.sources[0].url,
            fetched: s.sources[0].metadata?.fetched
          } : null
        }))
      });
      
      ragData.forEach((search, searchIdx) => {
        // Add search event
        events.push({
          type: 'search',
          timestamp: search.timestamp,
          content: search.query
        });
        
        // Filter to only show fetched sources (not snippets)
        const fetchedSources = search.sources.filter(source => {
          const wasFetched = source.metadata?.fetched === true ||
                            source.metadata?.fetch_status === 'success' ||
                            (source.content_preview && source.content_preview.includes('[Full Content Fetched]'));
          return wasFetched;
        });
        
        console.log(`[InlineResearchProgress] Search ${searchIdx} sources:`, {
          query: search.query,
          totalSources: search.sources.length,
          fetchedSources: fetchedSources.length
        });
        
        // Add fetched sources immediately after this query
        fetchedSources.forEach(source => {
          if (source.url || source.title) {
            events.push({
              type: 'read',
              timestamp: source.retrieved_at || search.timestamp,
              content: source.title || source.url || 'Unknown',
              url: source.url,
              favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ''),
              title: source.title
            });
          }
        });
      });
    } else {
      // DURING RESEARCH: Show all sources as they come in
      console.log('[InlineResearchProgress] Using during-research format');
      
      ragData.forEach((search) => {
        // Add search event
        events.push({
          type: 'search',
          timestamp: search.timestamp,
          content: search.query
        });
        
        // During research: show all sources (they're being added incrementally)
        search.sources.forEach(source => {
          if (source.url || source.title) {
            events.push({
              type: 'read',
              timestamp: source.retrieved_at || search.timestamp,
              content: source.title || source.url || 'Unknown',
              url: source.url,
              favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ''),
              title: source.title
            });
          }
        });
      });
    }
    
    console.log('[InlineResearchProgress] Final timeline events:', {
      totalEvents: events.length,
      searchEvents: events.filter(e => e.type === 'search').length,
      readEvents: events.filter(e => e.type === 'read').length
    });
    
    return events;
  }, [ragData, isComplete]);
  
  const hasTimeline = timelineEvents.length > 0;

  return (
    <div className="space-y-3 my-4">
      {stages.map((stage) => {
        const status = getStageStatus(stage.phase, progress.phase, isComplete);
        const Icon = stage.icon;
        const isCurrentStage = progress.phase === stage.phase;
        
        // Only show the currently active stage (hide completed and pending)
        if (status !== 'active') return null;

        return (
          <div key={stage.phase}>
            <div
              onClick={onClick}
              className="rounded-xl border transition-all duration-300 bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-700 shadow-sm cursor-pointer hover:border-primary"
            >
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-0.5 text-primary">
                      <Icon className="h-5 w-5 animate-pulse" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm">
                        {stage.label}
                      </h3>

                      {/* Progress bar for active stage - moved up below title */}
                      {isCurrentStage && (
                        <div className="mt-2">
                          <div className="h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300 ease-out"
                              style={{ width: `${Math.min(progress.progress_percentage, 100)}%` }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Status text for active stage */}
                      {isCurrentStage && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {progress.status_text}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Progress indicator */}
                  <div className="flex-shrink-0">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
      
      {/* Timeline Accordion - show outside stages loop (always visible when there's timeline data) */}
      {hasTimeline && (
        <div className="mt-2">
          <button
            onClick={handleToggleTimeline}
            className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
          >
            {isTimelineExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
            <span>Research Timeline</span>
          </button>
          
          {isTimelineExpanded && (
            <div className="mt-2 ml-1 space-y-2 border-l-2 border-gray-200 dark:border-gray-700 pl-3">
              {timelineEvents.map((event, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <div className="flex-shrink-0 mt-0.5">
                    {event.type === 'search' && (
                      <Search className="h-3 w-3 text-muted-foreground" />
                    )}
                    {event.type === 'read' && (() => {
                      if (event.favicon && event.favicon.trim() !== '') {
                        return (
                          <img
                            src={event.favicon}
                            alt=""
                            className="h-3 w-3 rounded"
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display = 'none';
                            }}
                          />
                        );
                      }
                      return <Globe className="h-3 w-3 text-muted-foreground" />;
                    })()}
                  </div>
                  
                  <div className="flex-1 min-w-0 text-xs">
                    {event.type === 'search' && (
                      <div>
                        <span className="font-medium text-gray-900 dark:text-gray-100">{event.content}</span>
                      </div>
                    )}
                    {event.type === 'read' && (
                      <div>
                        {event.url ? (
                          <a
                            href={event.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline font-medium"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {event.title || new URL(event.url).hostname}
                          </a>
                        ) : (
                          <span className="font-medium text-gray-900 dark:text-gray-100">{event.content}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default InlineResearchProgress;