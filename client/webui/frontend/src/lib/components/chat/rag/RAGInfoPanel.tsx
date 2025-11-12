import React from "react";
import { FileText, TrendingUp, Search, Database, ChevronDown, ChevronUp, Brain, Globe } from "lucide-react";
// Web-only version - enterprise icons removed
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/lib/components/ui/tabs";
import type { RAGSearchResult } from "@/lib/types";

interface TimelineEvent {
    type: 'thinking' | 'search' | 'read';
    timestamp: string;
    content: string;
    url?: string;
    favicon?: string;
    title?: string;
    source_type?: string;
}

interface RAGInfoPanelProps {
    ragData: RAGSearchResult[] | null;
    enabled: boolean;
}

/**
 * Extract clean filename from file_id by removing session prefix
 * Example: "sam_dev_user_web-session-xxx_filename.pdf_v0.pdf" -> "filename.pdf"
 */
const extractFilename = (filename: string | undefined): string => {
    if (!filename) return 'Unknown';
    
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
};

const SourceCard: React.FC<{
    source: RAGSearchResult['sources'][0];
}> = ({ source }) => {
    const [isExpanded, setIsExpanded] = React.useState(false);
    const contentPreview = source.content_preview;
    
    // Don't show content preview if it's just "Reading..." placeholder
    const hasRealContent = contentPreview && contentPreview !== 'Reading...';
    const shouldTruncate = hasRealContent && contentPreview.length > 200;
    const displayContent = shouldTruncate && !isExpanded
        ? contentPreview.substring(0, 200) + "..."
        : contentPreview;

    // Only show score if it's a real relevance score (not the default 1.0 from deep research)
    const showScore = source.relevance_score !== 1.0;

    return (
        <div className="bg-muted/50 p-3 rounded border border-border/50 flex flex-col">
            {/* Source Header */}
            <div className="flex items-center justify-between mb-2 flex-shrink-0">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                    <FileText className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                    <span className="font-medium text-xs truncate" title={source.title || source.filename || extractFilename(source.file_id)}>
                        {source.title || source.filename || extractFilename(source.file_id)}
                    </span>
                </div>
                {showScore && (
                    <div className="flex items-center gap-1 text-xs font-medium flex-shrink-0 ml-2">
                        <TrendingUp className="h-3 w-3" />
                        <span>Score: {source.relevance_score.toFixed(2)}</span>
                    </div>
                )}
            </div>

            {/* Content Preview - Fixed height when collapsed - Only show if we have real content */}
            {hasRealContent && (
                <div className={`text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap break-words overflow-hidden ${
                    isExpanded ? '' : 'h-[72px]'
                }`}>
                    {displayContent}
                </div>
            )}

            {/* Expand/Collapse Button */}
            {shouldTruncate && (
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="flex items-center gap-1 text-xs text-primary hover:underline mt-2 flex-shrink-0"
                >
                    {isExpanded ? (
                        <>
                            <ChevronUp className="h-3 w-3" />
                            Show less
                        </>
                    ) : (
                        <>
                            <ChevronDown className="h-3 w-3" />
                            Show more
                        </>
                    )}
                </button>
            )}

            {/* Metadata (if available) */}
            {source.metadata && Object.keys(source.metadata).length > 0 && (
                <div className="mt-2 pt-2 border-t border-border/50 flex-shrink-0">
                    <details className="text-xs">
                        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            Metadata
                        </summary>
                        <div className="mt-1 pl-2 space-y-1">
                            {Object.entries(source.metadata).map(([key, value]) => (
                                <div key={key} className="flex gap-2">
                                    <span className="font-medium">{key}:</span>
                                    <span className="text-muted-foreground">
                                        {typeof value === "object" ? JSON.stringify(value) : String(value)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </details>
                </div>
            )}
        </div>
    );
};

export const RAGInfoPanel: React.FC<RAGInfoPanelProps> = ({ ragData, enabled }) => {
    
    if (!enabled) {
        return (
            <div className="flex h-full items-center justify-center p-4">
                <div className="text-muted-foreground text-center">
                    <Database className="mx-auto mb-4 h-12 w-12 opacity-50" />
                    <div className="text-lg font-medium">RAG Sources</div>
                    <div className="mt-2 text-sm">
                        RAG source visibility is disabled in settings
                    </div>
                </div>
            </div>
        );
    }

    if (!ragData || ragData.length === 0) {
        return (
            <div className="flex h-full items-center justify-center p-4">
                <div className="text-muted-foreground text-center">
                    <Search className="mx-auto mb-4 h-12 w-12 opacity-50" />
                    <div className="text-lg font-medium">Sources</div>
                    <div className="mt-2 text-sm">
                        No sources available yet
                    </div>
                    <div className="mt-1 text-xs">
                        Sources from RAG searches and web research
                        <br />
                        will appear here after completion
                    </div>
                </div>
            </div>
        );
    }

    // Check if all data is deep_research (hide Sources tab if so)
    const isAllDeepResearch = ragData.every(search => search.search_type === 'deep_research');
    
    // Calculate total sources across all searches
    const totalSources = ragData.reduce((sum, search) => sum + search.sources.length, 0);
    
    return (
        <div className="h-full flex flex-col overflow-hidden">
            {isAllDeepResearch ? (
                // Deep research: Activity tab only (sources shown inline in chat)
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="px-4 pt-4 pb-2 flex-shrink-0">
                        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                            Research Activity
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
                        <div className="mb-3">
                            <p className="text-xs text-muted-foreground">
                                {ragData.length} search{ragData.length !== 1 ? "es" : ""} performed
                            </p>
                        </div>
                        
                        <div className="space-y-2">
                            {ragData.map((search, searchIdx) => {
                                // Build timeline events for this search
                                const events: TimelineEvent[] = [];
                                
                                // Add search event
                                events.push({
                                    type: 'search',
                                    timestamp: search.timestamp,
                                    content: search.query
                                });
                                
                                // Add read events for sources that were fetched/analyzed
                                search.sources.forEach(source => {
                                    if (source.url || source.title) {
                                        const sourceType = source.metadata?.source_type || 'web';
                                        events.push({
                                            type: 'read',
                                            timestamp: source.retrieved_at || search.timestamp,
                                            content: source.title || source.url || 'Unknown',
                                            url: source.url,
                                            favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ''),
                                            title: source.title,
                                            source_type: sourceType
                                        });
                                    }
                                });
                                
                                return (
                                    <React.Fragment key={searchIdx}>
                                        {events.map((event, eventIdx) => (
                                            <div key={`${searchIdx}-${eventIdx}`} className="flex items-start gap-3 py-2">
                                                {/* Icon */}
                                                <div className="flex-shrink-0 mt-0.5">
                                                    {event.type === 'thinking' && (
                                                        <Brain className="h-4 w-4 text-muted-foreground" />
                                                    )}
                                                    {event.type === 'search' && (
                                                        <Search className="h-4 w-4 text-muted-foreground" />
                                                    )}
                                                    {event.type === 'read' && (() => {
                                                        // Web-only version - only web sources
                                                        if (event.favicon && event.favicon.trim() !== '') {
                                                            // Web source with favicon
                                                            return (
                                                                <img
                                                                    src={event.favicon}
                                                                    alt=""
                                                                    className="h-4 w-4 rounded"
                                                                    onError={(e) => {
                                                                        (e.target as HTMLImageElement).style.display = 'none';
                                                                    }}
                                                                />
                                                            );
                                                        } else {
                                                            // Web source without favicon or unknown
                                                            return <Globe className="h-4 w-4 text-muted-foreground" />;
                                                        }
                                                    })()}
                                                </div>
                                                
                                                {/* Content */}
                                                <div className="flex-1 min-w-0">
                                                    {event.type === 'search' && (
                                                        <div className="text-sm">
                                                            <span className="text-muted-foreground">Searched for </span>
                                                            <span className="font-medium">{event.content}</span>
                                                        </div>
                                                    )}
                                                    {event.type === 'read' && (
                                                        <div className="text-sm">
                                                            <span className="text-muted-foreground">Read </span>
                                                            {event.url ? (
                                                                <a
                                                                    href={event.url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="text-primary hover:underline font-medium"
                                                                >
                                                                    {event.title || new URL(event.url).hostname}
                                                                </a>
                                                            ) : (
                                                                <span className="font-medium">{event.content}</span>
                                                            )}
                                                        </div>
                                                    )}
                                                    {event.type === 'thinking' && (
                                                        <div className="text-sm text-muted-foreground">
                                                            {event.content}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </React.Fragment>
                                );
                            })}
                        </div>
                    </div>
                </div>
            ) : (
                // Regular RAG/web search: Show both Activity and Sources tabs
                <Tabs defaultValue="activity" className="flex-1 flex flex-col overflow-hidden">
                    <div className="px-4 pt-4 pb-2 flex-shrink-0">
                        <TabsList className="grid w-full grid-cols-2">
                            <TabsTrigger value="activity">Activity</TabsTrigger>
                            <TabsTrigger value="sources">{totalSources} Sources</TabsTrigger>
                        </TabsList>
                    </div>
                
                <TabsContent value="activity" className="flex-1 overflow-y-auto px-4 pb-4 mt-0 min-h-0">
                    <div className="mb-3">
                        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                            Timeline of Research Activity
                        </h3>
                        <p className="text-xs text-muted-foreground mt-1">
                            {ragData.length} search{ragData.length !== 1 ? "es" : ""} performed
                        </p>
                    </div>
                    
                    <div className="space-y-2">
                        {ragData.map((search, searchIdx) => {
                            // Build timeline events for this search
                            const events: TimelineEvent[] = [];
                            
                            // Add search event
                            events.push({
                                type: 'search',
                                timestamp: search.timestamp,
                                content: search.query
                            });
                            
                            // Add read events for sources that were fetched/analyzed
                            search.sources.forEach(source => {
                                if (source.url || source.title) {
                                    const sourceType = source.metadata?.source_type || 'web';
                                    events.push({
                                        type: 'read',
                                        timestamp: source.retrieved_at || search.timestamp,
                                        content: source.title || source.url || 'Unknown',
                                        url: source.url,
                                        favicon: source.metadata?.favicon || (source.url ? `https://www.google.com/s2/favicons?domain=${source.url}&sz=32` : ''),
                                        title: source.title,
                                        source_type: sourceType
                                    });
                                }
                            });
                            
                            return (
                                <React.Fragment key={searchIdx}>
                                    {events.map((event, eventIdx) => (
                                        <div key={`${searchIdx}-${eventIdx}`} className="flex items-start gap-3 py-2">
                                            {/* Icon */}
                                            <div className="flex-shrink-0 mt-0.5">
                                                {event.type === 'thinking' && (
                                                    <Brain className="h-4 w-4 text-muted-foreground" />
                                                )}
                                                {event.type === 'search' && (
                                                    <Search className="h-4 w-4 text-muted-foreground" />
                                                )}
                                                {event.type === 'read' && (() => {
                                                    // Web-only version - only web sources
                                                    if (event.favicon && event.favicon.trim() !== '') {
                                                        // Web source with favicon
                                                        return (
                                                            <img
                                                                src={event.favicon}
                                                                alt=""
                                                                className="h-4 w-4 rounded"
                                                                onError={(e) => {
                                                                    (e.target as HTMLImageElement).style.display = 'none';
                                                                }}
                                                            />
                                                        );
                                                    } else {
                                                        // Web source without favicon or unknown
                                                        return <Globe className="h-4 w-4 text-muted-foreground" />;
                                                    }
                                                })()}
                                            </div>
                                            
                                            {/* Content */}
                                            <div className="flex-1 min-w-0">
                                                {event.type === 'search' && (
                                                    <div className="text-sm">
                                                        <span className="text-muted-foreground">Searched for </span>
                                                        <span className="font-medium">{event.content}</span>
                                                    </div>
                                                )}
                                                {event.type === 'read' && (
                                                    <div className="text-sm">
                                                        <span className="text-muted-foreground">Read </span>
                                                        {event.url ? (
                                                            <a
                                                                href={event.url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="text-primary hover:underline font-medium"
                                                            >
                                                                {event.title || new URL(event.url).hostname}
                                                            </a>
                                                        ) : (
                                                            <span className="font-medium">{event.content}</span>
                                                        )}
                                                    </div>
                                                )}
                                                {event.type === 'thinking' && (
                                                    <div className="text-sm text-muted-foreground">
                                                        {event.content}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </React.Fragment>
                            );
                        })}
                    </div>
                </TabsContent>
                
                <TabsContent value="sources" className="flex-1 overflow-y-auto px-4 pb-4 mt-0 min-h-0">
                    <div className="mb-3">
                        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                            All Sources
                        </h3>
                        <p className="text-xs text-muted-foreground mt-1">
                            {totalSources} source{totalSources !== 1 ? "s" : ""} found across {ragData.length} search{ragData.length !== 1 ? "es" : ""}
                        </p>
                    </div>
                    
                    <div className="space-y-2">
                        {ragData.map((search, searchIdx) =>
                            search.sources.map((source, sourceIdx) => (
                                <SourceCard key={`${searchIdx}-${sourceIdx}`} source={source} />
                            ))
                        )}
                    </div>
                </TabsContent>
                </Tabs>
            )}
        </div>
    );
};
