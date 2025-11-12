/**
 * Sources Display Component (Web-Only Version)
 * Shows web search results in a tabbed interface
 */

import { useMemo, useState, useEffect } from 'react';
import * as Ariakit from '@ariakit/react';
import { Globe, Image as ImageIcon } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/lib/components/ui/tabs';
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle } from '@/lib/components/ui/dialog';
import { StackedFavicons } from './StackedFavicons';
import { FaviconImage, getCleanDomain } from './Citation';
import type { RAGSource } from '@/lib/types/fe';

// Define types locally since we don't have the search types
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
  const domain = source.link ? getCleanDomain(source.link) : '';
  const [isDark, setIsDark] = useState(false);
  
  // Detect dark mode
  useEffect(() => {
    const checkDarkMode = () => {
      setIsDark(document.documentElement.classList.contains('dark'));
    };
    
    checkDarkMode();
    
    // Watch for theme changes
    const observer = new MutationObserver(checkDarkMode);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });
    
    return () => observer.disconnect();
  }, []);

  // Get appropriate icon for source type (web-only)
  const getSourceIcon = () => {
    return domain ? <FaviconImage domain={domain} /> : <Globe className="h-4 w-4 flex-shrink-0 text-muted-foreground" />;
  };

  // Get display label for source type (web-only)
  const getSourceLabel = () => {
    return domain || 'Web';
  };

  // Enterprise sources without URLs should not be clickable
  const isClickable = !!source.link;
  const CardWrapper = isClickable ? 'a' : 'div';
  const cardProps = isClickable ? {
    href: source.link,
    target: "_blank",
    rel: "noopener noreferrer"
  } : {};

  if (expanded) {
    return (
      <CardWrapper
        {...cardProps}
        className="flex w-full flex-col rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm transition-all duration-300 hover:bg-gray-100 dark:hover:bg-gray-700 overflow-hidden"
      >
        <div className="flex items-center gap-2 min-w-0 overflow-hidden">
          {getSourceIcon()}
          <span className="truncate text-xs font-medium text-gray-600 dark:text-gray-400">{getSourceLabel()}</span>
        </div>
        <div className="mt-1 min-w-0 overflow-hidden">
          <span className="line-clamp-2 text-sm font-medium text-gray-900 dark:text-gray-100 md:line-clamp-3 break-words overflow-hidden">
            {source.title || source.link || 'Untitled'}
          </span>
          {source.snippet && (
            <span className="mt-1 line-clamp-2 text-xs text-gray-600 dark:text-gray-400 md:line-clamp-3 break-words">
              {source.snippet}
            </span>
          )}
        </div>
      </CardWrapper>
    );
  }

  return (
    <span className="relative inline-block w-full">
      <Ariakit.HovercardProvider showTimeout={150} hideTimeout={150}>
        <span className="flex items-center w-full">
          <Ariakit.HovercardAnchor
            render={
              <CardWrapper
                {...cardProps}
                className="flex h-full w-full flex-col justify-between rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm transition-all duration-300 hover:bg-gray-100 dark:hover:bg-gray-700 overflow-hidden"
              >
                <div className="flex items-center gap-2 min-w-0 overflow-hidden">
                  {getSourceIcon()}
                  <span className="truncate text-xs font-medium text-gray-600 dark:text-gray-400">{getSourceLabel()}</span>
                </div>
                <div className="mt-1 min-w-0 overflow-hidden">
                  <span className="line-clamp-2 text-sm font-medium text-gray-900 dark:text-gray-100 md:line-clamp-3 break-words overflow-hidden">
                    {source.title || source.link || 'Untitled'}
                  </span>
                </div>
              </CardWrapper>
            }
          />
          
          <Ariakit.Hovercard
            gutter={8}
            className="z-[999] w-[300px] max-w-[calc(100vw-2rem)] rounded-xl border p-3 shadow-lg overflow-hidden"
            style={{
              backgroundColor: isDark ? '#1f2937' : '#ffffff',
              borderColor: isDark ? '#4b5563' : '#d1d5db',
              color: isDark ? '#f3f4f6' : '#111827'
            }}
            portal={true}
            unmountOnHide={true}
          >
            <span className="mb-2 flex items-center min-w-0 overflow-hidden">
              {getSourceIcon()}
              {isClickable ? (
                <a
                  href={source.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-2 line-clamp-2 cursor-pointer overflow-hidden text-sm font-bold text-[#0066cc] hover:underline dark:text-blue-400 md:line-clamp-3 truncate"
                >
                  {source.attribution || getSourceLabel()}
                </a>
              ) : (
                <span className="ml-2 line-clamp-2 overflow-hidden text-sm font-bold text-gray-900 dark:text-gray-100 md:line-clamp-3 truncate">
                  {source.attribution || getSourceLabel()}
                </span>
              )}
            </span>
            <h4 className="mb-1.5 mt-0 text-xs text-gray-900 dark:text-gray-100 md:text-sm overflow-hidden break-words">
              {source.title || source.link || 'Untitled'}
            </h4>
            {source.snippet && (
              <span className="my-2 text-ellipsis break-words text-xs text-gray-600 dark:text-gray-400 md:text-sm overflow-hidden">
                {source.snippet}
              </span>
            )}
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
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 w-full overflow-visible">
      {visibleSources.map((source, i) => (
        <div key={`source-${i}`} className="w-full min-w-[120px] h-full overflow-visible">
          <SourceCard source={source} />
        </div>
      ))}
      {hasMore && (
        <Dialog>
          <DialogTrigger className="flex flex-col rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm transition-all duration-300 hover:bg-gray-100 dark:hover:bg-gray-700">
            <div className="flex items-center gap-2">
              <StackedFavicons sources={remainingSources} end={3} />
              <span className="truncate text-xs font-medium text-gray-600 dark:text-gray-400">
                +{remainingSources.length} more
              </span>
            </div>
          </DialogTrigger>
          <DialogContent className="max-w-full md:max-w-[600px] max-h-[80vh] flex flex-col overflow-hidden">
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
  return (
    <a
      href={image.imageUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="group overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800 transition-all duration-300 hover:bg-gray-200 dark:hover:bg-gray-700"
    >
      <div className="relative aspect-square w-full overflow-hidden">
        <img
          src={image.imageUrl}
          alt={image.title || 'Search result image'}
          className="w-full h-full object-cover"
        />
        {image.title && (
          <div className="absolute bottom-0 left-0 right-0 w-full bg-gray-900/80 p-1 text-xs font-medium text-white backdrop-blur-sm">
            <span className="truncate">{image.title}</span>
          </div>
        )}
      </div>
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
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
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
      <span className="w-4 h-4">{icon}</span>
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
}

export function Sources({ ragMetadata }: SourcesProps & { ragMetadata?: { sources?: RAGSource[] } }) {
  // Process and categorize sources by type with deduplication
  const sourcesByType = useMemo(() => {
    if (!ragMetadata?.sources) {
      return {
        all: [],
        web: [],
        kb: [],
        images: []
      };
    }

    const categorized = {
      all: [] as SearchSource[],
      web: [] as SearchSource[],
      images: [] as ImageResult[]
    };

    // Track seen sources to avoid duplicates
    const seenSources = new Set<string>();

    ragMetadata.sources.forEach((s: RAGSource) => {
      const sourceType = s.metadata?.source_type || s.source_type || 'web';
      const source: SearchSource = {
        link: s.source_url || s.metadata?.link || '',
        title: s.metadata?.title || s.filename || '',
        snippet: s.content_preview || '',
        attribution: s.filename || '',
        processed: false,
        source_type: sourceType
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
  if (sourcesByType.all.length === 0) {
    return null;
  }

  // Determine which tabs to show based on available sources
  const tabs = [];
  if (sourcesByType.all.length > 0) {
    tabs.push({ value: 'all', label: 'All', icon: <Globe />, count: sourcesByType.all.length });
  }
  if (sourcesByType.web.length > 0) {
    tabs.push({ value: 'web', label: 'Web', icon: <Globe />, count: sourcesByType.web.length });
  }
  if (sourcesByType.images.length > 0) {
    tabs.push({ value: 'images', label: 'Images', icon: <ImageIcon />, count: sourcesByType.images.length });
  }

  // Default to first available tab
  const defaultTab = tabs[0]?.value || 'all';

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