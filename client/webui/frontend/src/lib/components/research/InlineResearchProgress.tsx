/**
 * Inline Research Progress Component
 *
 * Displays research stages building inline as they progress.
 * Each stage appears as a card that shows its status and details.
 */

import React, { useState } from "react";
import { Search, Brain, FileText, Globe, ChevronDown, ChevronUp, CheckCircle } from "lucide-react";
import type { RAGSearchResult } from "@/lib/types";
import { Button } from "@/lib/components/ui";

export interface ResearchProgressData {
    type: "deep_research_progress";
    phase: "planning" | "searching" | "analyzing" | "writing";
    status_text: string;
    progress_percentage: number;
    current_iteration: number;
    total_iterations: number;
    sources_found: number;
    current_query: string;
    fetching_urls: Array<{ url: string; title: string; favicon: string; source_type?: string }>;
    elapsed_seconds: number;
    max_runtime_seconds: number;
    // Query history for timeline display during research
    query_history?: Array<{
        query: string;
        timestamp: string;
        urls: Array<{ url: string; title: string; favicon: string; source_type?: string }>;
    }>;
}

interface InlineResearchProgressProps {
    progress: ResearchProgressData;
    isComplete?: boolean;
    ragData?: RAGSearchResult[];
}

interface StageInfo {
    phase: "planning" | "searching" | "analyzing" | "writing";
    icon: typeof Brain;
    label: string;
    description: string;
}

const stages: StageInfo[] = [
    {
        phase: "planning",
        icon: Brain,
        label: "Starting research",
        description: "Planning research strategy",
    },
    {
        phase: "searching",
        icon: Search,
        label: "Exploring sources",
        description: "Searching for relevant information",
    },
    {
        phase: "analyzing",
        icon: Brain,
        label: "Analyzing content",
        description: "Processing and analyzing sources",
    },
    {
        phase: "writing",
        icon: FileText,
        label: "Generating report",
        description: "Compiling final research",
    },
];

const getStageStatus = (stagePhase: string, currentPhase: string, isComplete: boolean): "pending" | "active" | "complete" => {
    const phaseOrder = ["planning", "searching", "analyzing", "writing"];
    const stageIndex = phaseOrder.indexOf(stagePhase);
    const currentIndex = phaseOrder.indexOf(currentPhase);

    if (isComplete && stagePhase === "writing") return "complete";
    if (stageIndex < currentIndex) return "complete";
    if (stageIndex === currentIndex) return "active";
    return "pending";
};

export const InlineResearchProgress: React.FC<InlineResearchProgressProps> = ({ progress, isComplete = false, ragData }) => {
    // Use localStorage to persist accordion state across navigation
    const storageKey = `research-timeline-expanded`;
    const [isTimelineExpanded, setIsTimelineExpanded] = useState(() => {
        const stored = localStorage.getItem(storageKey);
        return stored !== null ? stored === "true" : true; // Default to expanded
    });

    // Track scroll position for fade gradients
    const [showBottomGradient, setShowBottomGradient] = useState(false);
    const [showTopGradient, setShowTopGradient] = useState(false);
    const [showSpacing, setShowSpacing] = useState(true); // For animation delay
    const timelineRef = React.useRef<HTMLDivElement>(null);

    const handleToggleTimeline = (e: React.MouseEvent) => {
        e.stopPropagation();
        const newState = !isTimelineExpanded;
        setIsTimelineExpanded(newState);
        localStorage.setItem(storageKey, String(newState));

        // Delay hiding spacing until after collapse animation
        if (!newState) {
            setTimeout(() => setShowSpacing(false), 300); // Match animation duration
        } else {
            setShowSpacing(true);
        }
    };

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        const target = e.currentTarget;
        const hasOverflow = target.scrollHeight > target.clientHeight;
        const isAtBottom = Math.abs(target.scrollHeight - target.scrollTop - target.clientHeight) < 1;
        const isAtTop = target.scrollTop < 1;

        setShowBottomGradient(hasOverflow && !isAtBottom);
        setShowTopGradient(hasOverflow && !isAtTop);
    };

    // Build timeline events - use query_history from progress during research, ragData when complete
    const timelineEvents = React.useMemo(() => {
        const events: Array<{
            type: "search" | "read";
            timestamp: string;
            content: string;
            url?: string;
            favicon?: string;
            title?: string;
        }> = [];

        // DURING RESEARCH: Use query_history from progress data if available
        // This maintains the query→URLs relationship as queries are executed
        if (!isComplete && progress.query_history && progress.query_history.length > 0) {
            console.log("[InlineResearchProgress] Using query_history from progress:", {
                historyLength: progress.query_history.length,
                queries: progress.query_history.map(q => q.query),
            });

            progress.query_history.forEach(queryEntry => {
                // Add search event for this query
                events.push({
                    type: "search",
                    timestamp: queryEntry.timestamp,
                    content: queryEntry.query,
                });

                // Add read events for this query's URLs
                queryEntry.urls.forEach(urlInfo => {
                    events.push({
                        type: "read",
                        timestamp: queryEntry.timestamp,
                        content: urlInfo.title || urlInfo.url || "Unknown",
                        url: urlInfo.url,
                        favicon: urlInfo.favicon || (urlInfo.url ? `https://www.google.com/s2/favicons?domain=${urlInfo.url}&sz=32` : ""),
                        title: urlInfo.title,
                    });
                });
            });

            return events;
        }

        // COMPLETED or no query_history: Use ragData
        if (!ragData || ragData.length === 0) {
            console.log("[InlineResearchProgress] No ragData available");
            return [];
        }

        console.log("[InlineResearchProgress] Building timeline from ragData:", {
            ragDataCount: ragData.length,
            isComplete,
            firstSearchSample: ragData[0]
                ? {
                      query: ragData[0].query,
                      sourcesCount: ragData[0].sources?.length,
                      metadata: (ragData[0] as RAGSearchResult & { metadata?: Record<string, unknown> }).metadata,
                  }
                : null,
        });

        // Check if we have query breakdown in metadata (new backend format)
        const firstSearch = ragData[0];
        type ExtendedRAGSearchResult = RAGSearchResult & {
            metadata?: {
                queries?: Array<{
                    query: string;
                    timestamp: string;
                    sourceCitationIds: string[];
                }>;
            };
        };
        const metadata = (firstSearch as ExtendedRAGSearchResult)?.metadata;
        const hasQueryBreakdown = metadata?.queries && Array.isArray(metadata.queries);

        // Check if we have multiple ragData entries (one per query)
        const hasMultipleEntries = ragData.length > 1;

        if (hasQueryBreakdown) {
            // Use query breakdown from backend to maintain order
            const queries = metadata.queries as Array<{
                query: string;
                timestamp: string;
                sourceCitationIds: string[];
            }>;
            const allSources = firstSearch.sources;

            // Create a map of citationId to source for quick lookup
            const sourceMap = new Map();
            allSources.forEach(source => {
                if (source.citationId) {
                    sourceMap.set(source.citationId, source);
                }
            });

            queries.forEach((queryInfo: { query: string; timestamp: string; sourceCitationIds: string[] }) => {
                // Add search event
                events.push({
                    type: "search",
                    timestamp: queryInfo.timestamp,
                    content: queryInfo.query,
                });

                // Add read events for this query's fetched sources
                queryInfo.sourceCitationIds.forEach((citId: string) => {
                    const source = sourceMap.get(citId);
                    if (source) {
                        const wasFetched = source.metadata?.fetched === true || source.metadata?.fetch_status === "success" || (source.content_preview && source.content_preview.includes("[Full Content Fetched]"));

                        if (wasFetched && (source.url || source.title || source.metadata?.title)) {
                            const title = source.title || source.metadata?.title;
                            events.push({
                                type: "read",
                                timestamp: source.retrieved_at || queryInfo.timestamp,
                                content: title || source.url || "Unknown",
                                url: source.url,
                                favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ""),
                                title: title,
                            });
                        }
                    }
                });
            });
        } else if (hasMultipleEntries) {
            // Multiple ragData entries (one per query) - use this format
            console.log("[InlineResearchProgress] Using multiple entries format", {
                totalEntries: ragData.length,
                sampleEntries: ragData.slice(0, 3).map((s, i) => ({
                    index: i,
                    query: s.query,
                    sourcesCount: s.sources?.length,
                    timestamp: s.timestamp,
                    firstSourceSample: s.sources?.[0]
                        ? {
                              title: s.sources[0].title,
                              url: s.sources[0].url,
                              fetched: s.sources[0].metadata?.fetched,
                          }
                        : null,
                })),
            });

            ragData.forEach((search, searchIdx) => {
                // Add search event
                events.push({
                    type: "search",
                    timestamp: search.timestamp,
                    content: search.query,
                });

                // For completed research: filter to only show fetched sources (not snippets)
                // For in-progress: show all sources
                const sourcesToShow = isComplete
                    ? search.sources.filter(source => {
                          const wasFetched = source.metadata?.fetched === true || source.metadata?.fetch_status === "success" || (source.contentPreview && source.contentPreview.includes("[Full Content Fetched]"));
                          return wasFetched;
                      })
                    : search.sources;

                console.log(`[InlineResearchProgress] Search ${searchIdx} sources:`, {
                    query: search.query,
                    totalSources: search.sources.length,
                    shownSources: sourcesToShow.length,
                });

                // Add sources immediately after this query
                sourcesToShow.forEach(source => {
                    const title = source.title || source.metadata?.title;
                    if (source.url || title) {
                        events.push({
                            type: "read",
                            timestamp: source.retrievedAt || search.timestamp,
                            content: title || source.url || "Unknown",
                            url: source.url,
                            favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ""),
                            title: title,
                        });
                    }
                });
            });
        } else {
            // Single ragData entry - show query and all its sources
            console.log("[InlineResearchProgress] Using single entry format");

            const search = ragData[0];
            events.push({
                type: "search",
                timestamp: search.timestamp,
                content: search.query,
            });

            search.sources.forEach(source => {
                const title = source.title || source.metadata?.title;
                if (source.url || title) {
                    events.push({
                        type: "read",
                        timestamp: source.retrievedAt || search.timestamp,
                        content: title || source.url || "Unknown",
                        url: source.url,
                        favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ""),
                        title: title,
                    });
                }
            });
        }

        console.log("[InlineResearchProgress] Final timeline events:", {
            totalEvents: events.length,
            searchEvents: events.filter(e => e.type === "search").length,
            readEvents: events.filter(e => e.type === "read").length,
        });

        return events;
    }, [ragData, isComplete, progress.query_history]);

    const hasTimeline = timelineEvents.length > 0;

    // Check for overflow when timeline expands or content changes
    React.useEffect(() => {
        if (isTimelineExpanded && timelineRef.current) {
            const hasOverflow = timelineRef.current.scrollHeight > timelineRef.current.clientHeight;
            setShowBottomGradient(hasOverflow);
            setShowTopGradient(false); // Start at top, so no top gradient initially
        }
    }, [isTimelineExpanded, timelineEvents]);

    // Auto-scroll to bottom when new timeline events are added (during active research)
    React.useEffect(() => {
        if (!isComplete && isTimelineExpanded && timelineRef.current && timelineEvents.length > 0) {
            // Scroll to bottom smoothly when new events are added
            timelineRef.current.scrollTo({
                top: timelineRef.current.scrollHeight,
                behavior: "smooth",
            });
        }
    }, [timelineEvents.length, isComplete, isTimelineExpanded]);

    return (
        <div className="my-4 space-y-3">
            {/* Show completed state when research is done */}
            {isComplete ? (
                <div>
                    <div className="border-border bg-background rounded-lg border p-3">
                        <div className="flex items-start justify-between gap-3">
                            <div className="flex min-w-0 flex-1 items-start gap-3">
                                {/* Checkmark Icon */}
                                <div className="mt-0.5 flex-shrink-0 text-green-600 dark:text-green-400">
                                    <CheckCircle className="h-5 w-5" />
                                </div>

                                {/* Content */}
                                <div className="min-w-0 flex-1">
                                    <h3 className="text-sm font-medium">Research complete</h3>

                                    {/* Progress bar - full */}
                                    <div className={`mt-2 ${showSpacing ? "mb-4" : ""}`}>
                                        <div className="h-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                                            <div className="h-full bg-green-600 transition-all duration-300 ease-out dark:bg-green-400" style={{ width: "100%" }} />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Accordion Button - on the right */}
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={e => {
                                    e.stopPropagation();
                                    handleToggleTimeline(e);
                                }}
                                tooltip={isTimelineExpanded ? "Collapse" : "Expand"}
                            >
                                {isTimelineExpanded ? <ChevronUp className="h-4 w-4 transition-transform duration-200" /> : <ChevronDown className="h-4 w-4 transition-transform duration-200" />}
                            </Button>
                        </div>

                        {/* Expanded timeline section - full width with divider */}
                        {hasTimeline && (
                            <div className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${isTimelineExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
                                <div className="overflow-hidden">
                                    <div className="-mx-3">
                                        <hr className="border-t" />
                                    </div>
                                    <div className="p-3">
                                        <div className="relative">
                                            <div ref={timelineRef} className="max-h-[300px] space-y-2 overflow-y-auto" onScroll={handleScroll}>
                                                {(() => {
                                                    let currentSection: "search" | "read" | null = null;
                                                    return timelineEvents.map((event, idx) => {
                                                        const isNewSection = currentSection !== event.type;
                                                        currentSection = event.type;

                                                        return (
                                                            <React.Fragment key={idx}>
                                                                {/* Section header for grouped events */}
                                                                {isNewSection && <div className="mt-4 text-xs font-medium text-[var(--color-secondary-text-wMain)] first:mt-0">{event.type === "search" ? "Searching" : "Reviewing"}</div>}

                                                                <div className="flex items-start gap-2">
                                                                    <div className="mt-1 flex-shrink-0">
                                                                        {event.type === "search" && <Search className="text-muted-foreground h-3 w-3" />}
                                                                        {event.type === "read" &&
                                                                            (() => {
                                                                                if (event.favicon && event.favicon.trim() !== "") {
                                                                                    return (
                                                                                        <img
                                                                                            src={event.favicon}
                                                                                            alt=""
                                                                                            className="h-3 w-3 rounded"
                                                                                            onError={e => {
                                                                                                (e.target as HTMLImageElement).style.display = "none";
                                                                                            }}
                                                                                        />
                                                                                    );
                                                                                }
                                                                                return <Globe className="text-muted-foreground h-3 w-3" />;
                                                                            })()}
                                                                    </div>

                                                                    <div className="min-w-0 flex-1 text-sm">
                                                                        {event.type === "search" && (
                                                                            <div>
                                                                                <span className="font-medium text-gray-900 dark:text-gray-100">{event.content}</span>
                                                                            </div>
                                                                        )}
                                                                        {event.type === "read" && (
                                                                            <div>
                                                                                {event.url ? (
                                                                                    <a href={event.url} target="_blank" rel="noopener noreferrer" className="text-primary font-medium hover:underline" onClick={e => e.stopPropagation()}>
                                                                                        {event.title || event.url}
                                                                                    </a>
                                                                                ) : (
                                                                                    <span className="font-medium text-gray-900 dark:text-gray-100">{event.content}</span>
                                                                                )}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            </React.Fragment>
                                                        );
                                                    });
                                                })()}
                                            </div>
                                            {/* Fade gradient at top when scrolled down */}
                                            {showTopGradient && <div className="pointer-events-none absolute top-0 right-0 left-0 h-10 bg-gradient-to-b from-white to-transparent dark:from-gray-900" />}
                                            {/* Fade gradient at bottom to indicate more content */}
                                            {showBottomGradient && <div className="pointer-events-none absolute right-0 bottom-0 left-0 h-10 bg-gradient-to-t from-white to-transparent dark:from-gray-900" />}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                // Active state - show current stage
                stages.map(stage => {
                    const status = getStageStatus(stage.phase, progress.phase, isComplete);
                    const Icon = stage.icon;
                    const isCurrentStage = progress.phase === stage.phase;

                    // Only show the currently active stage (hide completed and pending)
                    if (status !== "active") return null;

                    return (
                        <div key={stage.phase}>
                            <div className="border-border bg-background rounded-lg border p-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex min-w-0 flex-1 items-start gap-3">
                                        {/* Icon */}
                                        <div className="text-primary mt-0.5 flex-shrink-0">
                                            <Icon className="h-5 w-5 animate-pulse" />
                                        </div>

                                        {/* Content */}
                                        <div className="min-w-0 flex-1">
                                            <h3 className="text-sm font-medium">
                                                {stage.label}: <span className="text-sm font-normal text-gray-500 dark:text-gray-400">{progress.status_text}</span>
                                            </h3>

                                            {/* Progress bar for active stage */}
                                            {isCurrentStage && (
                                                <div className={`mt-2 ${showSpacing ? "mb-4" : ""}`}>
                                                    <div className="h-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                                                        <div className="bg-primary h-full transition-all duration-300 ease-out" style={{ width: `${Math.min(progress.progress_percentage, 100)}%` }} />
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Accordion Button - on the right */}
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={e => {
                                            e.stopPropagation();
                                            handleToggleTimeline(e);
                                        }}
                                        tooltip={isTimelineExpanded ? "Collapse" : "Expand"}
                                    >
                                        {isTimelineExpanded ? <ChevronUp className="h-4 w-4 transition-transform duration-200" /> : <ChevronDown className="h-4 w-4 transition-transform duration-200" />}
                                    </Button>
                                </div>

                                {/* Expanded timeline section - full width with divider */}
                                {hasTimeline && (
                                    <div className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${isTimelineExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
                                        <div className="overflow-hidden">
                                            <div className="-mx-3">
                                                <hr className="border-t" />
                                            </div>
                                            <div className="p-3">
                                                <div className="relative">
                                                    <div ref={timelineRef} className="max-h-[300px] space-y-2 overflow-y-auto" onScroll={handleScroll}>
                                                        {(() => {
                                                            let currentSection: "search" | "read" | null = null;
                                                            return timelineEvents.map((event, idx) => {
                                                                const isNewSection = currentSection !== event.type;
                                                                currentSection = event.type;

                                                                return (
                                                                    <React.Fragment key={idx}>
                                                                        {/* Section header for grouped events */}
                                                                        {isNewSection && <div className="mt-4 text-xs font-medium text-[var(--color-secondary-text-wMain)] first:mt-0">{event.type === "search" ? "Searching" : "Reviewing"}</div>}

                                                                        <div className="flex items-start gap-2">
                                                                            <div className="mt-1 flex-shrink-0">
                                                                                {event.type === "search" && <Search className="text-muted-foreground h-3 w-3" />}
                                                                                {event.type === "read" &&
                                                                                    (() => {
                                                                                        if (event.favicon && event.favicon.trim() !== "") {
                                                                                            return (
                                                                                                <img
                                                                                                    src={event.favicon}
                                                                                                    alt=""
                                                                                                    className="h-3 w-3 rounded"
                                                                                                    onError={e => {
                                                                                                        (e.target as HTMLImageElement).style.display = "none";
                                                                                                    }}
                                                                                                />
                                                                                            );
                                                                                        }
                                                                                        return <Globe className="text-muted-foreground h-3 w-3" />;
                                                                                    })()}
                                                                            </div>

                                                                            <div className="min-w-0 flex-1 text-sm">
                                                                                {event.type === "search" && (
                                                                                    <div>
                                                                                        <span className="font-medium text-gray-900 dark:text-gray-100">{event.content}</span>
                                                                                    </div>
                                                                                )}
                                                                                {event.type === "read" && (
                                                                                    <div>
                                                                                        {event.url ? (
                                                                                            <a href={event.url} target="_blank" rel="noopener noreferrer" className="text-primary font-medium hover:underline" onClick={e => e.stopPropagation()}>
                                                                                                {event.title || event.url}
                                                                                            </a>
                                                                                        ) : (
                                                                                            <span className="font-medium text-gray-900 dark:text-gray-100">{event.content}</span>
                                                                                        )}
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                        </div>
                                                                    </React.Fragment>
                                                                );
                                                            });
                                                        })()}
                                                    </div>
                                                    {/* Fade gradient at top when scrolled down */}
                                                    {showTopGradient && <div className="pointer-events-none absolute top-0 right-0 left-0 h-10 bg-gradient-to-b from-white to-transparent dark:from-gray-900" />}
                                                    {/* Fade gradient at bottom to indicate more content */}
                                                    {showBottomGradient && <div className="pointer-events-none absolute right-0 bottom-0 left-0 h-10 bg-gradient-to-t from-white to-transparent dark:from-gray-900" />}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })
            )}
        </div>
    );
};

export default InlineResearchProgress;
