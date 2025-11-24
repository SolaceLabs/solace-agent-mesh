/**
 * Sources Display Component
 * Shows web search results in a tabbed interface
 */

import { useMemo, useState, useEffect } from "react";
import * as Ariakit from "@ariakit/react";
import { Globe, Image as ImageIcon } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/lib/components/ui/tabs";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { StackedFavicons } from "./StackedFavicons";
import { FaviconImage, getCleanDomain } from "./Citation";
import type { RAGSource } from "@/lib/types/fe";

interface SearchSource {
    link: string;
    title?: string;
    snippet?: string;
    attribution?: string;
    processed?: boolean;
    source_type?: string; // 'web'
}

interface ImageResult {
    imageUrl: string;
    title?: string;
}

/**
 * Individual source card
 */
interface SourceCardProps {
    source: SearchSource;
    expanded?: boolean;
}

function SourceCard({ source, expanded = false }: SourceCardProps) {
    const domain = source.link ? getCleanDomain(source.link) : "";
    const [isDark, setIsDark] = useState(false);

    // Detect dark mode
    useEffect(() => {
        const checkDarkMode = () => {
            setIsDark(document.documentElement.classList.contains("dark"));
        };

        checkDarkMode();

        // Watch for theme changes
        const observer = new MutationObserver(checkDarkMode);
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["class"],
        });

        return () => observer.disconnect();
    }, []);

    // Get appropriate icon for source type (web-only)
    const getSourceIcon = () => {
        return domain ? <FaviconImage domain={domain} /> : <Globe className="text-muted-foreground h-4 w-4 flex-shrink-0" />;
    };

    // Get display label for source type (web-only)
    const getSourceLabel = () => {
        return domain || "Web";
    };

    // Enterprise sources without URLs should not be clickable
    const isClickable = !!source.link;
    const CardWrapper = isClickable ? "a" : "div";
    const cardProps = isClickable
        ? {
              href: source.link,
              target: "_blank",
              rel: "noopener noreferrer",
          }
        : {};

    if (expanded) {
        return (
            <CardWrapper {...cardProps} className="flex w-full flex-col overflow-hidden rounded-lg bg-gray-50 px-3 py-2 text-sm transition-all duration-300 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700">
                <div className="flex min-w-0 items-center gap-2 overflow-hidden">
                    {getSourceIcon()}
                    <span className="truncate text-xs font-medium text-gray-600 dark:text-gray-400">{getSourceLabel()}</span>
                </div>
                <div className="mt-1 min-w-0 overflow-hidden">
                    <span className="line-clamp-2 overflow-hidden text-sm font-medium break-words text-gray-900 md:line-clamp-3 dark:text-gray-100">{source.title || source.link || "Untitled"}</span>
                    {source.snippet && <span className="mt-1 line-clamp-2 text-xs break-words text-gray-600 md:line-clamp-3 dark:text-gray-400">{source.snippet}</span>}
                </div>
            </CardWrapper>
        );
    }

    return (
        <span className="relative inline-block w-full">
            <Ariakit.HovercardProvider showTimeout={150} hideTimeout={150}>
                <span className="flex w-full items-center">
                    <Ariakit.HovercardAnchor
                        render={
                            <CardWrapper
                                {...cardProps}
                                className="flex h-full w-full flex-col justify-between overflow-hidden rounded-lg bg-gray-50 px-3 py-2 text-sm transition-all duration-300 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700"
                            >
                                <div className="flex min-w-0 items-center gap-2 overflow-hidden">
                                    {getSourceIcon()}
                                    <span className="truncate text-xs font-medium text-gray-600 dark:text-gray-400">{getSourceLabel()}</span>
                                </div>
                                <div className="mt-1 min-w-0 overflow-hidden">
                                    <span className="line-clamp-2 overflow-hidden text-sm font-medium break-words text-gray-900 md:line-clamp-3 dark:text-gray-100">{source.title || source.link || "Untitled"}</span>
                                </div>
                            </CardWrapper>
                        }
                    />

                    <Ariakit.Hovercard
                        gutter={8}
                        className="z-[999] w-[300px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border p-3 shadow-lg"
                        style={{
                            backgroundColor: isDark ? "#1f2937" : "#ffffff",
                            borderColor: isDark ? "#4b5563" : "#d1d5db",
                            color: isDark ? "#f3f4f6" : "#111827",
                        }}
                        portal={true}
                        unmountOnHide={true}
                    >
                        <span className="mb-2 flex min-w-0 items-center overflow-hidden">
                            {getSourceIcon()}
                            {isClickable ? (
                                <a href={source.link} target="_blank" rel="noopener noreferrer" className="ml-2 line-clamp-2 cursor-pointer truncate overflow-hidden text-sm font-bold text-[#0066cc] hover:underline md:line-clamp-3 dark:text-blue-400">
                                    {source.attribution || getSourceLabel()}
                                </a>
                            ) : (
                                <span className="ml-2 line-clamp-2 truncate overflow-hidden text-sm font-bold text-gray-900 md:line-clamp-3 dark:text-gray-100">{source.attribution || getSourceLabel()}</span>
                            )}
                        </span>
                        <h4 className="mt-0 mb-1.5 overflow-hidden text-xs break-words text-gray-900 md:text-sm dark:text-gray-100">{source.title || source.link || "Untitled"}</h4>
                        {source.snippet && <span className="my-2 overflow-hidden text-xs break-words text-ellipsis text-gray-600 md:text-sm dark:text-gray-400">{source.snippet}</span>}
                    </Ariakit.Hovercard>
                </span>
            </Ariakit.HovercardProvider>
        </span>
    );
}

/**
 * Grid of sources with "show more" dialog
 */
interface SourcesGridProps {
    sources: SearchSource[];
    limit?: number;
}

function SourcesGrid({ sources, limit = 4 }: SourcesGridProps) {
    const visibleSources = sources.slice(0, limit);
    const remainingSources = sources.slice(limit);
    const hasMore = remainingSources.length > 0;

    return (
        <div className="grid w-full grid-cols-2 gap-2 overflow-visible md:grid-cols-4">
            {visibleSources.map((source, i) => (
                <div key={`source-${i}`} className="h-full w-full min-w-[120px] overflow-visible">
                    <SourceCard source={source} />
                </div>
            ))}
            {hasMore && (
                <Dialog>
                    <DialogTrigger className="flex flex-col rounded-lg bg-gray-50 px-3 py-2 text-sm transition-all duration-300 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700">
                        <div className="flex items-center gap-2">
                            <StackedFavicons sources={remainingSources} end={3} />
                            <span className="truncate text-xs font-medium text-gray-600 dark:text-gray-400">+{remainingSources.length} more</span>
                        </div>
                    </DialogTrigger>
                    <DialogContent className="flex max-h-[80vh] max-w-full flex-col overflow-hidden md:max-w-[600px]">
                        <DialogHeader>
                            <DialogTitle>All Sources</DialogTitle>
                        </DialogHeader>
                        <div className="flex-1 overflow-y-auto px-3 py-2">
                            <div className="flex flex-col gap-2">
                                {[...visibleSources, ...remainingSources].map((source, i) => (
                                    <SourceCard key={`more-source-${i}`} source={source} expanded />
                                ))}
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </div>
    );
}

/**
 * Image result card
 */
interface ImageCardProps {
    image: ImageResult;
}

function ImageCard({ image }: ImageCardProps) {
    const [imageError, setImageError] = useState(false);

    if (imageError) {
        return (
            <div className="flex aspect-square w-full items-center justify-center overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800">
                <span className="text-xs text-gray-400">Failed to load</span>
            </div>
        );
    }

    return (
        <a href={image.imageUrl} target="_blank" rel="noopener noreferrer" className="group relative block aspect-square w-full overflow-hidden rounded-lg bg-gray-100 transition-all duration-300 hover:shadow-lg dark:bg-gray-800">
            <img src={image.imageUrl} alt={image.title || "Search result image"} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" onError={() => setImageError(true)} loading="lazy" />
            {image.title && (
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                    <span className="line-clamp-2 text-xs font-medium text-white">{image.title}</span>
                </div>
            )}
        </a>
    );
}

/**
 * Images grid
 */
interface ImagesGridProps {
    images: ImageResult[];
}

function ImagesGrid({ images }: ImagesGridProps) {
    return (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {images.map((image, i) => (
                <ImageCard key={`image-${i}`} image={image} />
            ))}
        </div>
    );
}

/**
 * Tab with icon
 */
interface TabWithIconProps {
    label: string;
    icon: React.ReactNode;
}

function TabWithIcon({ label, icon }: TabWithIconProps) {
    return (
        <div className="flex items-center gap-2">
            <span className="h-4 w-4">{icon}</span>
            <span>{label}</span>
        </div>
    );
}

/**
 * Main Sources Component
 * Displays search results in tabbed interface
 */
interface SourcesProps {
    messageId?: string;
    taskId?: string;
    isDeepResearch?: boolean;
    onDeepResearchClick?: () => void;
}

export function Sources({ ragMetadata, isDeepResearch = false, onDeepResearchClick }: SourcesProps & { ragMetadata?: { sources?: RAGSource[] } }) {
    // Process and categorize sources by type with deduplication
    const sourcesByType = useMemo(() => {
        if (!ragMetadata?.sources) {
            return {
                all: [],
                web: [],
                kb: [],
                images: [],
            };
        }

        const categorized = {
            all: [] as SearchSource[],
            web: [] as SearchSource[],
            images: [] as ImageResult[],
        };

        // Track seen sources to avoid duplicates
        const seenSources = new Set<string>();
        const seenImages = new Set<string>();

        ragMetadata.sources.forEach((s: RAGSource) => {
            const sourceType = s.sourceType || "web";

            // Handle image sources separately
            if (sourceType === "image" && s.metadata?.imageUrl) {
                const imageUrl = s.metadata.imageUrl;

                // Skip duplicate images
                if (seenImages.has(imageUrl)) {
                    return;
                }
                seenImages.add(imageUrl);

                const imageResult: ImageResult = {
                    imageUrl: imageUrl,
                    title: s.metadata?.title || s.filename || undefined,
                };

                categorized.images.push(imageResult);
                return;
            }

            // Handle regular web sources
            const source: SearchSource = {
                link: s.sourceUrl || s.metadata?.link || "",
                title: s.metadata?.title || s.filename || "",
                snippet: s.contentPreview || "",
                attribution: s.filename || "",
                processed: false,
                source_type: sourceType,
            };

            // Create a unique key for deduplication based on link and title
            const uniqueKey = `${sourceType}:${source.link}:${source.title}`;

            // Skip if we've already seen this source
            if (seenSources.has(uniqueKey)) {
                return;
            }
            seenSources.add(uniqueKey);

            // Add to all sources and web category (web-only)
            categorized.all.push(source);
            categorized.web.push(source);
        });

        return categorized;
    }, [ragMetadata]);

    // Don't render if no sources
    if (sourcesByType.all.length === 0 && sourcesByType.images.length === 0) {
        return null;
    }

    if (isDeepResearch || onDeepResearchClick || sourcesByType.web.length > 0) {
        const webSources = sourcesByType.web;
        const totalSources = webSources.length;

        console.log("[Sources] Stacked favicons:", {
            webSourcesCount: webSources.length,
            allSourcesCount: sourcesByType.all.length,
            imagesCount: sourcesByType.images.length,
            sampleWebSource: webSources[0],
        });

        // Don't render if no web sources (only images)
        if (totalSources === 0) {
            return null;
        }

        return (
            <div
                className={`flex items-center gap-2 rounded border border-[var(--color-secondary-w20)] px-2 py-1 ${onDeepResearchClick ? "cursor-pointer transition-colors hover:bg-[var(--color-secondary-w10)]" : ""}`}
                role={onDeepResearchClick ? "button" : undefined}
                aria-label={isDeepResearch ? "View deep research sources" : "View web search sources"}
                onClick={onDeepResearchClick}
            >
                <StackedFavicons sources={webSources} end={3} size={16} />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                    {totalSources} {totalSources === 1 ? "source" : "sources"}
                </span>
            </div>
        );
    }

    // Determine which tabs to show based on available sources
    const tabs = [];
    const hasWebSources = sourcesByType.web.length > 0;
    const hasImages = sourcesByType.images.length > 0;

    console.log("[Sources] Render decision:", { hasWebSources, hasImages, webCount: sourcesByType.web.length, imageCount: sourcesByType.images.length });

    // Only show tabs if we have both web sources and images
    if (hasWebSources && hasImages) {
        tabs.push({ value: "web", label: "Web", icon: <Globe />, count: sourcesByType.web.length });
        tabs.push({ value: "images", label: "Images", icon: <ImageIcon />, count: sourcesByType.images.length });
    }

    // Default to images tab if we have images, otherwise web
    const defaultTab = hasImages ? "images" : "web";

    // If only web sources (no images), show sources directly without tabs
    if (hasWebSources && !hasImages) {
        console.log("[Sources] Rendering web sources only");
        return (
            <div className="my-4" role="region" aria-label="Search sources">
                <SourcesGrid sources={sourcesByType.web} />
            </div>
        );
    }

    // If only images (no web sources), show images directly without tabs
    if (hasImages && !hasWebSources) {
        console.log("[Sources] Rendering images only:", sourcesByType.images);
        return (
            <div className="my-4" role="region" aria-label="Search images">
                <ImagesGrid images={sourcesByType.images} />
            </div>
        );
    }

    // If we have both, show tabs
    console.log("[Sources] Rendering tabs with both web and images");

    return (
        <div className="my-4" role="region" aria-label="Search sources">
            <Tabs defaultValue={defaultTab}>
                <TabsList>
                    {tabs.map(tab => (
                        <TabsTrigger key={tab.value} value={tab.value}>
                            <TabWithIcon label={`${tab.label} (${tab.count})`} icon={tab.icon} />
                        </TabsTrigger>
                    ))}
                </TabsList>

                <TabsContent value="all">
                    <SourcesGrid sources={sourcesByType.all} />
                </TabsContent>

                {sourcesByType.web.length > 0 && (
                    <TabsContent value="web">
                        <SourcesGrid sources={sourcesByType.web} />
                    </TabsContent>
                )}

                {/* Web-only version - no enterprise source tabs */}

                {sourcesByType.images.length > 0 && (
                    <TabsContent value="images">
                        <ImagesGrid images={sourcesByType.images} />
                    </TabsContent>
                )}
            </Tabs>
        </div>
    );
}

export default Sources;
