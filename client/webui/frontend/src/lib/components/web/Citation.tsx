/**
 * Citation Components
 * Renders inline citations with hover cards for web search and file sources
 */

/* eslint-disable react-refresh/only-export-components */
import React, { useState, useEffect, useRef, useCallback } from "react";
import type { ReactNode } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { cn, getCleanDomain, getFaviconUrl } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/lib/components/ui/popover";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";

// Re-export for backward compatibility
export { getCleanDomain, getFaviconUrl } from "@/lib/utils";

/**
 * Favicon image component
 */
export function FaviconImage({ domain, className = "" }: { domain: string; className?: string }) {
    return (
        <div className={cn("relative h-4 w-4 flex-shrink-0 overflow-hidden rounded-full bg-white", className)}>
            <img src={getFaviconUrl(domain)} alt={domain} className="relative h-full w-full" />
            <div className="absolute inset-0 rounded-full border border-gray-200/10 dark:border-transparent" />
        </div>
    );
}

/**
 * Source Hovercard Component
 * Displays citation information in a hover card with Radix UI Popover
 */
interface SourceHovercardProps {
    source: {
        link?: string;
        attribution?: string;
        title?: string;
        snippet?: string;
    };
    label: string;
    onMouseEnter?: () => void;
    onMouseLeave?: () => void;
    onClick?: (e: React.MouseEvent) => void;
    isFile?: boolean;
    isLocalFile?: boolean;
    children?: ReactNode;
}

function SourceHovercard({ source, label, onMouseEnter, onMouseLeave, onClick, isFile = false, isLocalFile = false, children }: SourceHovercardProps) {
    const domain = getCleanDomain(source.link || "");
    const [isOpen, setIsOpen] = useState(false);
    const [isDark, setIsDark] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const showTimeout = 150;
    const hideTimeout = 150;

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

    // Cleanup timeout on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    const handleMouseEnter = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            setIsOpen(true);
        }, showTimeout);
        onMouseEnter?.();
    }, [onMouseEnter]);

    const handleMouseLeave = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            setIsOpen(false);
        }, hideTimeout);
        onMouseLeave?.();
    }, [onMouseLeave]);

    const handleContentMouseEnter = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
    }, []);

    const handleContentMouseLeave = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            setIsOpen(false);
        }, hideTimeout);
    }, []);

    return (
        <span className="relative ml-0.5 inline-block">
            <Popover open={isOpen} onOpenChange={setIsOpen}>
                <span className="flex items-center">
                    <PopoverTrigger asChild>
                        {isFile ? (
                            <button
                                onClick={onClick}
                                onMouseEnter={handleMouseEnter}
                                onMouseLeave={handleMouseLeave}
                                className="border-border-heavy bg-surface-secondary hover:bg-surface-hover dark:border-border-medium dark:hover:bg-surface-tertiary ml-1 inline-block h-5 max-w-36 cursor-pointer items-center overflow-hidden rounded-xl border px-2 text-xs font-medium text-ellipsis whitespace-nowrap text-blue-600 no-underline transition-colors dark:text-blue-400"
                                title={isLocalFile ? "Download unavailable for local files" : undefined}
                            >
                                {label}
                            </button>
                        ) : (
                            <a
                                href={source.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                onMouseEnter={handleMouseEnter}
                                onMouseLeave={handleMouseLeave}
                                className="border-border-heavy bg-surface-secondary hover:bg-surface-hover dark:border-border-medium dark:hover:bg-surface-tertiary ml-1 inline-flex h-5 max-w-36 cursor-pointer items-center gap-1 overflow-hidden rounded-xl border px-2 text-xs font-medium no-underline transition-colors"
                            >
                                <span className="truncate">{label}</span>
                                <ExternalLink className="h-3 w-3 flex-shrink-0 opacity-60" />
                            </a>
                        )}
                    </PopoverTrigger>
                    <button
                        onClick={() => setIsOpen(!isOpen)}
                        onMouseEnter={handleMouseEnter}
                        onMouseLeave={handleMouseLeave}
                        className="text-text-primary focus:ring-ring ml-0.5 rounded-full focus:ring-2 focus:outline-none"
                        aria-label={`More details about ${label}`}
                    >
                        <VisuallyHidden>More details about {label}</VisuallyHidden>
                        <ChevronDown className="h-4 w-4" />
                    </button>

                    <PopoverContent
                        sideOffset={16}
                        onMouseEnter={handleContentMouseEnter}
                        onMouseLeave={handleContentMouseLeave}
                        className="z-[999] w-[300px] max-w-[calc(100vw-2rem)] rounded-xl border p-3 shadow-lg"
                        style={{
                            backgroundColor: isDark ? "#1f2937" : "#ffffff",
                            borderColor: isDark ? "#4b5563" : "#d1d5db",
                            color: isDark ? "#f3f4f6" : "#111827",
                        }}
                    >
                        {children}
                        {!children && (
                            <>
                                <span className="mb-2 flex items-center">
                                    {isFile ? (
                                        <div className="mr-2 flex h-4 w-4 items-center justify-center">
                                            <svg className="text-text-secondary h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                                            </svg>
                                        </div>
                                    ) : (
                                        <FaviconImage domain={domain} className="mr-2" />
                                    )}
                                    {isFile ? (
                                        <button onClick={onClick} className="line-clamp-2 cursor-pointer overflow-hidden text-left text-sm font-bold text-[#0066cc] hover:underline md:line-clamp-3 dark:text-blue-400">
                                            {source.attribution || source.title || "File Source"}
                                        </button>
                                    ) : (
                                        <a
                                            href={source.link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="line-clamp-2 inline-flex cursor-pointer items-center gap-1 overflow-hidden text-sm font-bold text-[#0066cc] hover:underline md:line-clamp-3 dark:text-blue-400"
                                        >
                                            <span className="truncate">{source.attribution || domain}</span>
                                            <ExternalLink className="h-3 w-3 flex-shrink-0" />
                                        </a>
                                    )}
                                </span>

                                {isFile ? (
                                    <>{source.snippet && <span className="text-text-secondary my-2 text-xs break-all text-ellipsis md:text-sm">{source.snippet}</span>}</>
                                ) : (
                                    <>
                                        <h4 className="text-text-primary mt-0 mb-1.5 text-xs md:text-sm">{source.title || source.link}</h4>
                                        {source.snippet && <span className="text-text-secondary my-2 text-xs break-all text-ellipsis md:text-sm">{source.snippet}</span>}
                                    </>
                                )}
                            </>
                        )}
                    </PopoverContent>
                </span>
            </Popover>
        </span>
    );
}

// Export just the utility components we need
export default SourceHovercard;
