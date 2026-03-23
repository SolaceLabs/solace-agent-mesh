import { useState, useMemo, useCallback, useEffect, useContext, useRef, memo } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Download, Trash2, File, MoreHorizontal, MessageCircle, Eye, EyeOff, FileImage, FileCode, FileText, Presentation, FolderOpen, X, AlertTriangle, ArrowUp, ArrowDown } from "lucide-react";
import {
    Button,
    Input,
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
    Spinner,
    Card,
    Tooltip,
    TooltipContent,
    TooltipTrigger,
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import { useAllArtifacts } from "@/lib/api/artifacts";
import { api } from "@/lib/api";
import { formatTimestamp, cn, createLruCache, getArtifactUrl, getArtifactContent, createSemaphore } from "@/lib/utils";
import { ARTIFACT_TAG_WORKING } from "@/lib/constants";
import { formatBytes } from "@/lib/utils/format";
import { DocumentThumbnail, supportsThumbnail } from "@/lib/components/chat/file/DocumentThumbnail";
import { ProjectBadge } from "@/lib/components/chat/file/ProjectBadge";
import { getFileTypeColor } from "@/lib/components/chat/file/FileIcon";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { canPreviewArtifact, getFileContent, getRenderType } from "@/lib/components/chat/preview/previewUtils";
import { Header } from "@/lib/components/header/Header";
import { LifecycleBadge } from "@/lib/components/ui";
import type { FileAttachment } from "@/lib/types";
import type { ArtifactWithSession } from "@/lib/api/artifacts";

// LRU Cache for document content with max size to prevent memory leaks
const documentContentCache = createLruCache<string>(50);

// LRU Cache for text preview snippets — avoids re-fetching full text files just for tile previews
const textPreviewCache = createLruCache<string>(200);

// Generate cache key for document content
function getDocumentCacheKey(sessionId: string, filename: string): string {
    return `${sessionId}:${filename}`;
}

/**
 * Concurrency limiter for preview fetches.
 * Browsers typically allow ~6 concurrent connections per origin.
 * We cap at 4 to leave headroom for user-initiated requests (navigation, downloads, etc.).
 */
const { release: releaseFetchSlot, acquireOrAbort: acquireFetchSlotOrAbort } = createSemaphore(4);

// Helper to check if artifact is a project artifact
// Note: Backend uses "project-{id}" format, but we also check "project:{id}" for backward compatibility
function isProjectArtifact(artifact: ArtifactWithSession): boolean {
    return artifact.sessionId.startsWith("project:") || artifact.sessionId.startsWith("project-") || artifact.source === "project";
}

/**
 * Helper to get the correct API URL for an artifact.
 *
 * NOTE: For project artifacts, we use "null" as a placeholder session ID in the URL path
 * because the backend artifacts endpoint requires a session_id path parameter.
 * The actual project is identified via the project_id query parameter.
 * This is a known API design quirk - ideally there would be a separate endpoint
 * like /api/v1/projects/{project_id}/artifacts/{filename} for project artifacts.
 */
function getArtifactApiUrl(artifact: ArtifactWithSession): string {
    if (isProjectArtifact(artifact) && artifact.projectId) {
        // Project artifacts use "null" as session placeholder with project_id query param
        return `/api/v1/artifacts/null/${encodeURIComponent(artifact.filename)}?project_id=${encodeURIComponent(artifact.projectId)}`;
    }
    return `/api/v1/artifacts/${artifact.sessionId}/${encodeURIComponent(artifact.filename)}`;
}

/**
 * Get file extension from filename
 */
function getFileExtension(filename: string): string {
    const parts = filename.split(".");
    return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
}

/**
 * Maximum bytes to request from the backend for text tile previews.
 * The backend's `max_bytes` query parameter truncates the response server-side,
 * so even a 5 MB CSV only transfers ~2 KB over the wire.
 */
const TEXT_PREVIEW_MAX_BYTES = 2048;

/**
 * Check if a MIME type supports text preview
 */
function supportsTextPreview(mimeType: string): boolean {
    return (
        mimeType.startsWith("text/") ||
        mimeType.includes("json") ||
        mimeType.includes("xml") ||
        mimeType.includes("javascript") ||
        mimeType.includes("typescript") ||
        mimeType.includes("markdown") ||
        mimeType.includes("yaml") ||
        mimeType.includes("yml")
    );
}

/**
 * Check if a MIME type is an image
 */
function isImageType(mimeType: string): boolean {
    return mimeType.startsWith("image/");
}

interface ArtifactGridCardProps {
    artifact: ArtifactWithSession;
    onDownload: (artifact: ArtifactWithSession) => void;
    onDelete: (artifact: ArtifactWithSession) => void;
    onPreview: (artifact: ArtifactWithSession) => void;
    onGoToChat: (artifact: ArtifactWithSession) => void;
    onGoToProject: (artifact: ArtifactWithSession) => void;
    isSelected?: boolean;
    /** Whether binary artifact preview (Office docs) is enabled */
    binaryArtifactPreviewEnabled: boolean;
}

const ArtifactGridCard = memo(function ArtifactGridCard({ artifact, onDownload, onDelete, onPreview, onGoToChat, onGoToProject, isSelected, binaryArtifactPreviewEnabled }: ArtifactGridCardProps) {
    const [contentPreview, setContentPreview] = useState<string | null>(() => {
        // Initialise from cache synchronously so cached tiles never flash a spinner
        const cacheKey = getDocumentCacheKey(artifact.sessionId, artifact.filename);
        return textPreviewCache.get(cacheKey) ?? null;
    });
    const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
    const [documentContent, setDocumentContent] = useState<string | null>(() => {
        const cacheKey = getDocumentCacheKey(artifact.sessionId, artifact.filename);
        return documentContentCache.get(cacheKey) ?? null;
    });
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);
    const [documentThumbnailFailed, setDocumentThumbnailFailed] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [isVisible, setIsVisible] = useState(false);
    const cardRef = useRef<HTMLDivElement>(null);

    // Check if this file supports document thumbnail
    const isDocumentThumbnailSupported = supportsThumbnail(artifact.filename, artifact.mime_type);

    // Check if file is a PDF (doesn't need conversion service)
    const isPdfFile = artifact.mime_type === "application/pdf" || artifact.filename.toLowerCase().endsWith(".pdf");

    // Only enable document thumbnail if: it's a PDF (always works) OR it's an Office doc and conversion is enabled
    const canAttemptDocumentThumbnail = isDocumentThumbnailSupported && (isPdfFile || binaryArtifactPreviewEnabled);

    // Determine whether this card needs a network fetch for its preview
    const needsPreviewFetch = isImageType(artifact.mime_type) || canAttemptDocumentThumbnail || supportsTextPreview(artifact.mime_type);

    // Use IntersectionObserver to defer ALL preview loading until card is near the viewport.
    // This prevents hundreds of simultaneous fetches when the page first loads with many artifacts.
    useEffect(() => {
        const el = cardRef.current;
        if (!el) return;

        // If this card type doesn't need a fetch at all, mark visible immediately
        if (!needsPreviewFetch) {
            setIsVisible(true);
            return;
        }

        // If content is already cached, no need to wait for visibility
        const cacheKey = getDocumentCacheKey(artifact.sessionId, artifact.filename);
        if (documentContentCache.get(cacheKey) || textPreviewCache.get(cacheKey)) {
            setIsVisible(true);
            return;
        }

        const observer = new IntersectionObserver(
            entries => {
                if (entries[0].isIntersecting) {
                    setIsVisible(true);
                    observer.disconnect();
                }
            },
            { rootMargin: "200px" }
        );
        observer.observe(el);
        return () => observer.disconnect();
    }, [needsPreviewFetch, artifact.sessionId, artifact.filename]);

    // Load content preview for text files, image thumbnail, or document thumbnail.
    // Gated behind isVisible (IntersectionObserver) AND a concurrency semaphore to
    // avoid overwhelming the browser's connection pool.
    useEffect(() => {
        // Defer ALL preview loading until card is visible
        if (!isVisible) return;

        // Track if component is still mounted
        let isMounted = true;
        const abortController = new AbortController();
        let imageBlobUrl: string | null = null;

        /** Acquire a semaphore slot, run `fn`, and release the slot when done. */
        async function fetchWithSlot<T>(signal: AbortSignal, fn: () => Promise<T>): Promise<T | undefined> {
            const acquired = await acquireFetchSlotOrAbort(signal);
            if (!acquired) return undefined;
            try {
                return await fn();
            } finally {
                releaseFetchSlot();
            }
        }

        const loadPreview = async () => {
            // Get the correct API URL for this artifact (handles both session and project artifacts)
            const artifactApiUrl = getArtifactApiUrl(artifact);

            if (isImageType(artifact.mime_type)) {
                // For images, fetch via authenticated API client and create a blob URL.
                await fetchWithSlot(abortController.signal, async () => {
                    const response = await api.webui.get(artifactApiUrl, { fullResponse: true, signal: abortController.signal });
                    if (abortController.signal.aborted) return;
                    if (response.ok) {
                        const blob = await response.blob();
                        if (abortController.signal.aborted) return;
                        imageBlobUrl = URL.createObjectURL(blob);
                        if (isMounted) setImagePreviewUrl(imageBlobUrl);
                    }
                });
            } else if (canAttemptDocumentThumbnail) {
                // For PDF, DOCX, PPTX, etc. - check cache first, then fetch content for thumbnail
                const cacheKey = getDocumentCacheKey(artifact.sessionId, artifact.filename);
                const cachedContent = documentContentCache.get(cacheKey);

                if (cachedContent) {
                    // Use cached content
                    if (isMounted) setDocumentContent(cachedContent);
                    return;
                }

                if (isMounted) setIsLoadingPreview(true);

                // Wrap only the network calls so the slot is released before local FileReader work
                const blob = await fetchWithSlot(abortController.signal, async () => {
                    const response = await api.webui.get(artifactApiUrl, { fullResponse: true, signal: abortController.signal });
                    if (abortController.signal.aborted) return undefined;

                    const b = await response.blob();
                    if (abortController.signal.aborted) return undefined;
                    return b;
                });

                if (!blob) return;

                try {
                    // Note: FileReader.readAsDataURL cannot be cancelled - it will complete in the background.
                    // The isMounted/abortController checks after this prevent state updates on unmounted components.
                    const base64data = await new Promise<string>((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => {
                            if (typeof reader.result === "string") {
                                resolve(reader.result.split(",")[1]);
                            } else {
                                reject(new Error("Failed to read content as data URL"));
                            }
                        };
                        reader.onerror = () => {
                            reject(reader.error || new Error("Unknown error reading file"));
                        };
                        reader.readAsDataURL(blob);
                    });

                    if (abortController.signal.aborted) return;

                    // Cache the content
                    documentContentCache.set(cacheKey, base64data);

                    if (isMounted) {
                        setDocumentContent(base64data);
                        setIsLoadingPreview(false);
                    }
                } catch (error) {
                    if (!abortController.signal.aborted) {
                        console.error("Error loading document content:", error);
                        if (isMounted) setIsLoadingPreview(false);
                    }
                }
            } else if (supportsTextPreview(artifact.mime_type)) {
                // For text files — check cache first, then fetch a preview snippet
                const cacheKey = getDocumentCacheKey(artifact.sessionId, artifact.filename);
                const cachedPreview = textPreviewCache.get(cacheKey);

                if (cachedPreview) {
                    if (isMounted) setContentPreview(cachedPreview);
                    return;
                }

                if (isMounted) setIsLoadingPreview(true);

                await fetchWithSlot(abortController.signal, async () => {
                    // Append max_bytes to request only the first ~2 KB from the backend.
                    // This avoids downloading multi-MB files just for an 8-line tile snippet.
                    const separator = artifactApiUrl.includes("?") ? "&" : "?";
                    const previewUrl = `${artifactApiUrl}${separator}max_bytes=${TEXT_PREVIEW_MAX_BYTES}`;
                    const response = await api.webui.get(previewUrl, { fullResponse: true, signal: abortController.signal });
                    if (abortController.signal.aborted) return;

                    const text = await response.text();
                    if (abortController.signal.aborted) return;

                    // Take first 500 chars and first 8 lines for preview
                    const preview = text
                        .substring(0, 500)
                        .split("\n")
                        .slice(0, 8)
                        .map(line => {
                            // Truncate long lines
                            return line.length > 50 ? line.substring(0, 50) + "..." : line;
                        })
                        .join("\n");

                    // Cache the text snippet so subsequent renders are instant
                    textPreviewCache.set(cacheKey, preview);

                    if (isMounted) {
                        setContentPreview(preview);
                        setIsLoadingPreview(false);
                    }
                });
            }
        };

        loadPreview().catch(error => {
            if (!abortController.signal.aborted) {
                console.error("Error loading preview:", error);
                if (isMounted) setIsLoadingPreview(false);
            }
        });

        return () => {
            isMounted = false;
            abortController.abort();
            // Revoke any blob URL created for image preview to free memory
            if (imageBlobUrl) {
                URL.revokeObjectURL(imageBlobUrl);
            }
        };
    }, [artifact.sessionId, artifact.filename, artifact.mime_type, canAttemptDocumentThumbnail, isVisible]);

    // Handle document thumbnail error - fall back to icon
    const handleDocumentThumbnailError = useCallback(() => {
        setDocumentThumbnailFailed(true);
    }, []);

    // Determine if we should show document thumbnail
    const canShowDocumentThumbnail = canAttemptDocumentThumbnail && !documentThumbnailFailed;

    const handleCardClick = () => {
        onPreview(artifact);
    };

    return (
        <Card
            className={cn(
                "group relative flex h-[220px] w-[320px] flex-shrink-0 cursor-pointer flex-col gap-0 overflow-hidden transition-all",
                "hover:bg-(--primary-w10)",
                "focus-visible:border-(--brand-w100) focus-visible:outline-none",
                isSelected && "border-(--brand-w100)"
            )}
            onClick={handleCardClick}
            onKeyDown={e => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleCardClick();
                }
            }}
            role="button"
            tabIndex={0}
            noPadding
        >
            {/* Header with filename, project badge, and menu */}
            <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
                <div className="flex min-w-0 flex-1 items-center gap-2">
                    <h3 className="min-w-0 flex-1 truncate text-sm font-semibold" title={artifact.filename}>
                        {artifact.filename}
                    </h3>
                    {artifact.projectName && <ProjectBadge text={artifact.projectName} className="flex-shrink-0" />}
                </div>
                <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                    <DropdownMenuTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 flex-shrink-0 p-0"
                            onClick={e => {
                                e.stopPropagation();
                                setDropdownOpen(!dropdownOpen);
                            }}
                        >
                            <MoreHorizontal size={14} />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48" onClick={e => e.stopPropagation()}>
                        {isProjectArtifact(artifact) ? (
                            <DropdownMenuItem
                                onClick={e => {
                                    e.stopPropagation();
                                    setDropdownOpen(false);
                                    onGoToProject(artifact);
                                }}
                            >
                                <FolderOpen size={14} className="mr-2" />
                                Go to Project
                            </DropdownMenuItem>
                        ) : (
                            <DropdownMenuItem
                                onClick={e => {
                                    e.stopPropagation();
                                    setDropdownOpen(false);
                                    onGoToChat(artifact);
                                }}
                            >
                                <MessageCircle size={14} className="mr-2" />
                                Go to Chat
                            </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                setDropdownOpen(false);
                                onDownload(artifact);
                            }}
                        >
                            <Download size={14} className="mr-2" />
                            Download
                        </DropdownMenuItem>
                        {/* Don't allow deleting project artifacts from here - they should be managed in the project */}
                        {!isProjectArtifact(artifact) && (
                            <DropdownMenuItem
                                onClick={e => {
                                    e.stopPropagation();
                                    setDropdownOpen(false);
                                    onDelete(artifact);
                                }}
                            >
                                <Trash2 size={14} className="mr-2" />
                                Delete
                            </DropdownMenuItem>
                        )}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>

            {/* Content Preview Area - takes most of the space */}
            <div ref={cardRef} className="relative flex flex-1 items-center justify-center overflow-hidden bg-(--secondary-w10)">
                {imagePreviewUrl ? (
                    <img src={imagePreviewUrl} alt={artifact.filename} className="h-full w-full object-cover" onError={() => setImagePreviewUrl(null)} />
                ) : canShowDocumentThumbnail && documentContent ? (
                    <DocumentThumbnail content={documentContent} filename={artifact.filename} mimeType={artifact.mime_type} width={320} height={130} onError={handleDocumentThumbnailError} className="absolute inset-0 h-full w-full" />
                ) : contentPreview ? (
                    <div className="h-full w-full overflow-hidden px-3 py-2 font-mono text-[11px] leading-relaxed text-(--secondary-text-wMain)">
                        {contentPreview.split("\n").map((line, index) => (
                            <div key={index} className="truncate">
                                {line || "\u00A0"}
                            </div>
                        ))}
                    </div>
                ) : isLoadingPreview ? (
                    <Spinner size="small" variant="muted" />
                ) : (
                    <div className="flex flex-col items-center justify-center gap-2">
                        {isImageType(artifact.mime_type) ? (
                            <FileImage className="h-12 w-12 text-(--secondary-text-wMain)" />
                        ) : supportsTextPreview(artifact.mime_type) ? (
                            <FileCode className="h-12 w-12 text-(--secondary-text-wMain)" />
                        ) : isDocumentThumbnailSupported ? (
                            // Show appropriate icon for document types while loading or if thumbnail failed
                            artifact.mime_type.includes("pdf") ? (
                                <FileText className="h-12 w-12 text-(--secondary-text-wMain)" />
                            ) : artifact.mime_type.includes("presentation") || artifact.filename.toLowerCase().endsWith(".pptx") || artifact.filename.toLowerCase().endsWith(".ppt") ? (
                                <Presentation className="h-12 w-12 text-(--secondary-text-wMain)" />
                            ) : (
                                <FileText className="h-12 w-12 text-(--secondary-text-wMain)" />
                            )
                        ) : (
                            <File className="h-12 w-12 text-(--secondary-text-wMain)" />
                        )}
                        {artifact.description && <span className="px-4 text-center text-xs text-(--secondary-text-wMain)">{artifact.description}</span>}
                    </div>
                )}

                {/* Hover overlay with preview button */}
                <div className="overlay-backdrop absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="secondary"
                                size="sm"
                                className="h-8 w-8 rounded-full p-0"
                                onClick={e => {
                                    e.stopPropagation();
                                    onPreview(artifact);
                                }}
                            >
                                <Eye className="h-4 w-4" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>Preview</TooltipContent>
                    </Tooltip>
                </div>
            </div>

            {/* Footer with metadata and extension badge */}
            <div className="flex items-center justify-between border-t px-3 py-2">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-(--secondary-text-wMain)">{formatBytes(artifact.size)}</span>
                    <span className="text-xs text-(--secondary-text-wMain)">•</span>
                    <span className="text-xs text-(--secondary-text-wMain)">{formatTimestamp(artifact.last_modified)}</span>
                </div>
                {/* Extension badge - uses shared getFileTypeColor from FileIcon */}
                <span className={cn("ml-3 flex-shrink-0 rounded px-2 py-0.5 text-[10px] font-bold text-(--darkSurface-text)", getFileTypeColor(artifact.mime_type, artifact.filename))}>
                    {getFileExtension(artifact.filename).length > 4 ? getFileExtension(artifact.filename).substring(0, 4) : getFileExtension(artifact.filename)}
                </span>
            </div>
        </Card>
    );
});

/**
 * Standalone preview panel for artifacts page
 * Fetches and displays artifact content directly without requiring chat context
 */
interface StandalonePreviewPanelProps {
    artifact: ArtifactWithSession;
    onClose: () => void;
    onDownload: (artifact: ArtifactWithSession) => void;
    onGoToChat: (artifact: ArtifactWithSession) => void;
    onGoToProject: (artifact: ArtifactWithSession) => void;
}

const StandalonePreviewPanel = memo(function StandalonePreviewPanel({ artifact, onClose, onDownload, onGoToChat, onGoToProject }: StandalonePreviewPanelProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<FileAttachment | null>(null);
    const [availableVersions, setAvailableVersions] = useState<number[]>([]);
    const [currentVersion, setCurrentVersion] = useState<number | null>(null);

    // Cache of version number → FileAttachment so switching versions is instant
    const versionCache = useRef<Map<number, FileAttachment>>(new Map());

    // Check if preview is supported
    const preview = useMemo(() => canPreviewArtifact(artifact), [artifact]);

    // Determine session/project context for API calls
    const sessionId = isProjectArtifact(artifact) ? undefined : artifact.sessionId;
    const projectId = isProjectArtifact(artifact) ? artifact.projectId : undefined;

    // Build a FileAttachment for a given version's fetched content
    const buildFileAttachment = useCallback(
        (content: string, mimeType: string, version: number): FileAttachment => {
            const artifactUrl = getArtifactUrl({ filename: artifact.filename, sessionId, projectId, version });
            return {
                name: artifact.filename,
                mime_type: mimeType,
                content,
                last_modified: artifact.last_modified,
                url: api.webui.getFullUrl(artifactUrl),
            };
        },
        [artifact.filename, artifact.last_modified, sessionId, projectId]
    );

    // Helper function to fetch content for a specific version
    const fetchContentForVersion = useCallback(
        async (version: number | "latest") => {
            // Serve from cache instantly — no spinner, no flash
            if (typeof version === "number" && versionCache.current.has(version)) {
                setFileContent(versionCache.current.get(version)!);
                return;
            }

            setIsLoading(true);
            setError(null);
            // Keep old fileContent visible (overlay spinner) while the new version loads

            try {
                const { content, mimeType } = await getArtifactContent({ filename: artifact.filename, sessionId, projectId, version });
                const resolvedVersion = typeof version === "number" ? version : (currentVersion ?? 0);
                const file = buildFileAttachment(content, mimeType, resolvedVersion);
                if (typeof version === "number") versionCache.current.set(version, file);
                setFileContent(file);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load artifact content");
            } finally {
                setIsLoading(false);
            }
        },
        [artifact.filename, sessionId, projectId, currentVersion, buildFileAttachment]
    );

    // Fetch available versions and initial content when artifact changes
    useEffect(() => {
        let isMounted = true;
        versionCache.current.clear();

        async function initialize() {
            setAvailableVersions([]);
            setCurrentVersion(null);
            setFileContent(null);
            setError(null);

            if (!preview?.canPreview) {
                setIsLoading(false);
                return;
            }

            setIsLoading(true);

            try {
                // Fetch available versions
                const versionsUrl = getArtifactUrl({ filename: artifact.filename, sessionId, projectId });
                const versions: number[] = await api.webui.get(versionsUrl);

                if (!isMounted) return;

                if (versions && versions.length > 0) {
                    const sortedVersions = versions.sort((a, b) => a - b);
                    const latestVersion = Math.max(...sortedVersions);
                    setAvailableVersions(sortedVersions);
                    setCurrentVersion(latestVersion);

                    // Fetch content for the latest version
                    const { content, mimeType } = await getArtifactContent({ filename: artifact.filename, sessionId, projectId, version: latestVersion });
                    if (!isMounted) return;

                    const file = buildFileAttachment(content, mimeType, latestVersion);
                    versionCache.current.set(latestVersion, file);
                    setFileContent(file);

                    // Pre-fetch adjacent versions (latest ± 1) in the background so switching is instant.
                    // We intentionally limit pre-fetching to avoid firing N-1 parallel requests
                    // when an artifact has many versions.
                    const latestIdx = sortedVersions.indexOf(latestVersion);
                    const adjacentVersions = [sortedVersions[latestIdx - 1], sortedVersions[latestIdx + 1]].filter((v): v is number => v !== undefined && v !== latestVersion);
                    for (const version of adjacentVersions) {
                        getArtifactContent({ filename: artifact.filename, sessionId, projectId, version })
                            .then(({ content: c, mimeType: mt }) => {
                                if (!isMounted) return;
                                versionCache.current.set(version, buildFileAttachment(c, mt, version));
                            })
                            .catch(() => {
                                /* ignore background pre-fetch errors */
                            });
                    }
                } else {
                    setAvailableVersions([]);
                }
            } catch (err) {
                if (isMounted) {
                    setError(err instanceof Error ? err.message : "Failed to load artifact");
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        }

        initialize();

        return () => {
            isMounted = false;
        };
    }, [artifact.filename, sessionId, projectId, preview?.canPreview, buildFileAttachment]);

    // Handle version change — instant if cached, overlay spinner if not yet cached
    const handleVersionChange = useCallback(
        async (version: string) => {
            const versionNum = parseInt(version, 10);
            setCurrentVersion(versionNum);
            await fetchContentForVersion(versionNum);
        },
        [fetchContentForVersion]
    );

    // Get renderer type and content - memoize to prevent re-renders when Select opens
    const rendererType = useMemo(() => getRenderType(artifact.filename, artifact.mime_type), [artifact.filename, artifact.mime_type]);
    const content = useMemo(() => getFileContent(fileContent), [fileContent]);
    const effectiveUrl = fileContent?.url;

    // Memoize the content renderer to prevent re-renders when Select dropdown opens
    const memoizedContentRenderer = useMemo(() => {
        if (!preview?.canPreview || !rendererType || !content) return null;
        return <ContentRenderer content={content} rendererType={rendererType} mime_type={artifact.mime_type} url={effectiveUrl} filename={artifact.filename} setRenderError={setError} />;
    }, [content, rendererType, artifact.mime_type, effectiveUrl, artifact.filename, preview?.canPreview]);

    return (
        <div className="flex h-full flex-col border-l">
            {/* Compact Header - filename, metadata, actions, and close button in one bar */}
            <div className="flex items-center gap-3 border-b px-3 py-2">
                {/* Left side: filename, version selector, and metadata */}
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3 className="truncate text-sm font-semibold" title={artifact.filename}>
                            {artifact.filename}
                        </h3>
                        {artifact.projectName && <ProjectBadge text={artifact.projectName} className="flex-shrink-0" />}
                        {/* Version Selector - only show when there are multiple versions */}
                        {availableVersions.length > 1 && currentVersion !== null && (
                            <Select value={currentVersion.toString()} onValueChange={handleVersionChange}>
                                <SelectTrigger className="h-[16px] py-0 text-xs shadow-none">
                                    <SelectValue placeholder="Version" />
                                </SelectTrigger>
                                <SelectContent>
                                    {availableVersions.map(version => (
                                        <SelectItem key={version} value={version.toString()}>
                                            Version {version}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                        <span>{formatBytes(artifact.size)}</span>
                        <span>•</span>
                        <span>{formatTimestamp(artifact.last_modified)}</span>
                    </div>
                </div>

                {/* Right side: action buttons and close */}
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => onDownload(artifact)}>
                        <Download className="mr-1 h-4 w-4" />
                        Download
                    </Button>
                    {isProjectArtifact(artifact) ? (
                        <Button variant="ghost" size="sm" onClick={() => onGoToProject(artifact)}>
                            <FolderOpen className="mr-1 h-4 w-4" />
                            Go to Project
                        </Button>
                    ) : (
                        <Button variant="ghost" size="sm" onClick={() => onGoToChat(artifact)}>
                            <MessageCircle className="mr-1 h-4 w-4" />
                            Go to Chat
                        </Button>
                    )}
                    <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Content Area */}
            <div className="min-h-0 flex-1 overflow-auto">
                {/* Full-screen spinner only during initial load (no content yet) */}
                {isLoading && !memoizedContentRenderer && (
                    <div className="flex h-full items-center justify-center">
                        <Spinner size="medium" variant="muted" />
                    </div>
                )}

                {error && (
                    <div className="flex h-full flex-col items-center justify-center p-4">
                        <div className="mb-2 text-sm text-(--error-wMain)">Error loading preview</div>
                        <div className="text-xs text-(--secondary-text-wMain)">{error}</div>
                    </div>
                )}

                {!isLoading && !error && !preview?.canPreview && (
                    <div className="flex h-full flex-col items-center justify-center p-4">
                        <File className="mb-4 h-12 w-12 text-(--secondary-text-wMain)" />
                        <div className="text-sm text-(--secondary-text-wMain)">{preview?.reason || "Preview not available"}</div>
                        <Button variant="default" className="mt-4" onClick={() => onDownload(artifact)}>
                            <Download className="mr-2 h-4 w-4" />
                            Download File
                        </Button>
                    </div>
                )}

                {memoizedContentRenderer && (
                    <div className="relative h-full w-full">
                        {memoizedContentRenderer}
                        {/* Overlay spinner during version switching — keeps old content visible */}
                        {isLoading && (
                            <div className="overlay-backdrop absolute inset-0 flex items-center justify-center">
                                <Spinner size="medium" variant="muted" />
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
});

// Sort options for artifacts
type SortField = "date" | "name" | "type" | "size";
type SortDirection = "asc" | "desc";

const SORT_OPTIONS: { value: SortField; label: string }[] = [
    { value: "date", label: "Date" },
    { value: "name", label: "Name" },
    { value: "type", label: "Type" },
    { value: "size", label: "Size" },
];

const SHOW_INTERNAL_ARTIFACTS_KEY = "sam_show_internal_artifacts";

function isInternalArtifact(artifact: ArtifactWithSession): boolean {
    return artifact.tags?.some(t => t.toLowerCase() === ARTIFACT_TAG_WORKING.toLowerCase()) ?? false;
}

export function ArtifactsPage() {
    const navigate = useNavigate();
    const { addNotification, displayError, handleSwitchSession } = useChatContext();
    const { data: artifacts = [], isLoading, error: fetchError, refetch } = useAllArtifacts();
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedProject, setSelectedProject] = useState<string>("all");
    const [sortBy, setSortBy] = useState<SortField>("date");
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
    const [previewArtifact, setPreviewArtifact] = useState<ArtifactWithSession | null>(null);
    const [deleteConfirmArtifact, setDeleteConfirmArtifact] = useState<ArtifactWithSession | null>(null);
    const [showInternalArtifacts, setShowInternalArtifacts] = useState<boolean>(() => {
        try {
            return localStorage.getItem(SHOW_INTERNAL_ARTIFACTS_KEY) === "true";
        } catch {
            return false;
        }
    });

    const toggleShowInternalArtifacts = useCallback(() => {
        setShowInternalArtifacts(prev => {
            const next = !prev;
            try {
                localStorage.setItem(SHOW_INTERNAL_ARTIFACTS_KEY, String(next));
            } catch {
                // ignore
            }
            return next;
        });
    }, []);

    // Get feature flags from config context
    const config = useContext(ConfigContext);
    const artifactsPageEnabled = config?.configFeatureEnablement?.artifactsPage ?? false;
    const binaryArtifactPreviewEnabled = config?.binaryArtifactPreviewEnabled ?? false;

    // Redirect to chat if feature is disabled
    useEffect(() => {
        if (!artifactsPageEnabled && config !== null) {
            navigate("/chat", { replace: true });
        }
    }, [artifactsPageEnabled, navigate, config]);

    // Get unique project names from artifacts, sorted alphabetically
    const projectNames = useMemo(() => {
        const uniqueProjectNames = new Set<string>();
        let hasUnassignedArtifacts = false;

        artifacts.forEach(artifact => {
            if (artifact.projectName) {
                uniqueProjectNames.add(artifact.projectName);
            } else {
                hasUnassignedArtifacts = true;
            }
        });

        const sortedNames = Array.from(uniqueProjectNames).sort((a, b) => a.localeCompare(b));

        if (hasUnassignedArtifacts) {
            sortedNames.unshift("(No Project)");
        }

        return sortedNames;
    }, [artifacts]);

    // Count internal artifacts (those with working tag) for display in toggle
    const internalArtifactCount = useMemo(() => {
        return artifacts.filter(isInternalArtifact).length;
    }, [artifacts]);

    // Filter and sort artifacts by project, search query, internal toggle, and sort options
    const filteredArtifacts = useMemo(() => {
        // Single-pass filter combining project, internal, and search criteria to avoid intermediate arrays
        const trimmedQuery = searchQuery.trim().toLowerCase();

        const filtered = artifacts.filter(artifact => {
            // Internal artifact filter — hide by default unless toggle is on
            if (!showInternalArtifacts && isInternalArtifact(artifact)) return false;

            // Project filter
            if (selectedProject !== "all") {
                if (selectedProject === "(No Project)") {
                    if (artifact.projectName) return false;
                } else {
                    if (artifact.projectName !== selectedProject) return false;
                }
            }

            // Search filter
            if (trimmedQuery) {
                const filename = artifact.filename.toLowerCase();
                const mimeType = artifact.mime_type.toLowerCase();
                const sessionName = artifact.sessionName?.toLowerCase() || "";
                const projectName = artifact.projectName?.toLowerCase() || "";
                if (!(filename.includes(trimmedQuery) || mimeType.includes(trimmedQuery) || sessionName.includes(trimmedQuery) || projectName.includes(trimmedQuery))) {
                    return false;
                }
            }

            return true;
        });

        // Sort artifacts (sort in-place since filter() already created a new array)
        filtered.sort((a, b) => {
            let comparison = 0;

            switch (sortBy) {
                case "date": {
                    // Sort by last_modified date
                    const dateA = a.last_modified ? new Date(a.last_modified).getTime() : 0;
                    const dateB = b.last_modified ? new Date(b.last_modified).getTime() : 0;
                    comparison = dateA - dateB;
                    break;
                }
                case "name":
                    // Sort by filename (case-insensitive)
                    comparison = a.filename.toLowerCase().localeCompare(b.filename.toLowerCase());
                    break;
                case "type": {
                    // Sort by file extension
                    const extA = a.filename.split(".").pop()?.toLowerCase() || "";
                    const extB = b.filename.split(".").pop()?.toLowerCase() || "";
                    comparison = extA.localeCompare(extB);
                    break;
                }
                case "size":
                    // Sort by file size
                    comparison = a.size - b.size;
                    break;
            }

            // Apply sort direction
            return sortDirection === "asc" ? comparison : -comparison;
        });

        return filtered;
    }, [artifacts, selectedProject, searchQuery, sortBy, sortDirection, showInternalArtifacts]);

    // Toggle sort direction or change sort field
    const handleSortChange = useCallback(
        (field: SortField) => {
            if (field === sortBy) {
                // Toggle direction if same field
                setSortDirection(prev => (prev === "asc" ? "desc" : "asc"));
            } else {
                // Change field and set default direction
                setSortBy(field);
                // Default to desc for date/size (newest/largest first), asc for name/type (A-Z)
                setSortDirection(field === "date" || field === "size" ? "desc" : "asc");
            }
        },
        [sortBy]
    );

    const handleDownload = useCallback(
        async (artifact: ArtifactWithSession) => {
            try {
                // Use the correct API URL for project vs session artifacts
                const apiUrl = getArtifactApiUrl(artifact);
                // Fetch the artifact content using full response
                const response = await api.webui.get(apiUrl, { fullResponse: true });
                const blob = await response.blob();

                // Create download link
                const downloadUrl = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = downloadUrl;
                link.download = artifact.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(downloadUrl);

                addNotification?.(`Downloaded ${artifact.filename}`, "success");
            } catch (error) {
                console.error("Error downloading artifact:", error);
                displayError?.({
                    title: "Download Failed",
                    error: error instanceof Error ? error.message : "Failed to download artifact",
                });
            }
        },
        [addNotification, displayError]
    );

    // Show delete confirmation dialog
    const handleDeleteRequest = useCallback(
        (artifact: ArtifactWithSession) => {
            // Don't allow deleting project artifacts from here
            if (isProjectArtifact(artifact)) {
                displayError?.({
                    title: "Cannot Delete",
                    error: "Project artifacts must be deleted from the project page",
                });
                return;
            }
            setDeleteConfirmArtifact(artifact);
        },
        [displayError]
    );

    // Actually perform the delete after confirmation
    const handleDeleteConfirm = useCallback(async () => {
        if (!deleteConfirmArtifact) return;

        try {
            await api.webui.delete(`/api/v1/artifacts/${deleteConfirmArtifact.sessionId}/${encodeURIComponent(deleteConfirmArtifact.filename)}`);
            addNotification?.(`Deleted ${deleteConfirmArtifact.filename}`, "success");
            setDeleteConfirmArtifact(null);
            refetch();
        } catch (error) {
            console.error("Error deleting artifact:", error);
            displayError?.({
                title: "Delete Failed",
                error: error instanceof Error ? error.message : "Failed to delete artifact",
            });
            setDeleteConfirmArtifact(null);
        }
    }, [deleteConfirmArtifact, addNotification, displayError, refetch]);

    const handlePreview = useCallback((artifact: ArtifactWithSession) => {
        // Open the preview panel directly on this page
        setPreviewArtifact(artifact);
    }, []);

    const handleClosePreview = useCallback(() => setPreviewArtifact(null), []);

    const handleGoToChat = useCallback(
        async (artifact: ArtifactWithSession) => {
            // Switch to the artifact's session and navigate to chat
            await handleSwitchSession(artifact.sessionId);
            navigate("/chat");
        },
        [navigate, handleSwitchSession]
    );

    const handleGoToProject = useCallback(
        (artifact: ArtifactWithSession) => {
            // Navigate to the project page
            if (artifact.projectId) {
                navigate(`/projects/${artifact.projectId}`);
            }
        },
        [navigate]
    );

    return (
        <div className="flex h-full flex-col">
            {/* Page Header - using shared Header component for consistent styling */}
            <Header
                title={
                    <>
                        Artifacts <LifecycleBadge>EXPERIMENTAL</LifecycleBadge>
                    </>
                }
            />

            {/* Content area with optional preview panel */}
            <div className="flex min-h-0 flex-1">
                {/* Main content area */}
                <div className={cn("flex min-h-0 flex-col transition-all", previewArtifact ? "w-1/2" : "w-full")}>
                    <div className="flex h-full flex-col gap-4 py-6 pl-6">
                        {/* Search and Project Filter on same line */}
                        <div className="flex items-center gap-4 pr-4">
                            {/* Search Input */}
                            <div className="relative w-64">
                                <Search className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-(--secondary-text-wMain)" />
                                <Input type="text" placeholder="Search artifacts..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="pl-9" />
                            </div>

                            {/* Project Filter - Only show when there are projects */}
                            {projectNames.length > 0 && (
                                <div className="flex items-center gap-2">
                                    <label className="text-sm font-medium whitespace-nowrap">Project:</label>
                                    <Select value={selectedProject} onValueChange={setSelectedProject}>
                                        <SelectTrigger className="w-40 rounded-md">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Artifacts</SelectItem>
                                            {projectNames.map(projectName => (
                                                <SelectItem key={projectName} value={projectName}>
                                                    {projectName}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}

                            {/* Sort Controls */}
                            <div className="flex items-center gap-2">
                                <label className="text-sm font-medium whitespace-nowrap">Sort:</label>
                                <div className="flex items-center">
                                    <Select value={sortBy} onValueChange={(value: SortField) => handleSortChange(value)}>
                                        <SelectTrigger className="h-9 w-24 rounded-r-none border-r-0">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {SORT_OPTIONS.map(option => (
                                                <SelectItem key={option.value} value={option.value}>
                                                    {option.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Button variant="outline" size="icon" className="h-9 w-9 rounded-l-none" onClick={() => setSortDirection(prev => (prev === "asc" ? "desc" : "asc"))} title={sortDirection === "asc" ? "Ascending" : "Descending"}>
                                        {sortDirection === "asc" ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>

                            {!isLoading && artifacts.length > 0 && (
                                <span className="text-sm text-(--secondary-text-wMain)">
                                    {filteredArtifacts.length} artifact{filteredArtifacts.length !== 1 ? "s" : ""}
                                    {(searchQuery || selectedProject !== "all" || !showInternalArtifacts) && filteredArtifacts.length !== artifacts.length && ` (of ${artifacts.length})`}
                                </span>
                            )}

                            {/* Internal artifacts toggle — only show when there are internal artifacts */}
                            {!isLoading && internalArtifactCount > 0 && (
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button variant={showInternalArtifacts ? "secondary" : "ghost"} size="sm" onClick={toggleShowInternalArtifacts} className="flex items-center gap-1.5">
                                            {showInternalArtifacts ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            {showInternalArtifacts ? "Hide Internal" : `Show Internal (${internalArtifactCount})`}
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        {showInternalArtifacts ? "Hide internal/working files generated by agents" : `Show ${internalArtifactCount} internal/working file${internalArtifactCount !== 1 ? "s" : ""} generated by agents`}
                                    </TooltipContent>
                                </Tooltip>
                            )}
                        </div>

                        <div className="flex-1 overflow-y-auto pr-4">
                            {isLoading && (
                                <div className="flex h-full items-center justify-center">
                                    <Spinner size="large" variant="muted" />
                                </div>
                            )}

                            {!isLoading && filteredArtifacts.length > 0 && (
                                <div className="flex flex-wrap gap-4">
                                    {filteredArtifacts.map(artifact => (
                                        <ArtifactGridCard
                                            key={`${artifact.sessionId}-${artifact.filename}-${artifact.version || 0}`}
                                            artifact={artifact}
                                            onDownload={handleDownload}
                                            onDelete={handleDeleteRequest}
                                            onPreview={handlePreview}
                                            onGoToChat={handleGoToChat}
                                            onGoToProject={handleGoToProject}
                                            isSelected={previewArtifact?.filename === artifact.filename && previewArtifact?.sessionId === artifact.sessionId}
                                            binaryArtifactPreviewEnabled={binaryArtifactPreviewEnabled}
                                        />
                                    ))}
                                </div>
                            )}

                            {!isLoading && filteredArtifacts.length === 0 && artifacts.length > 0 && (
                                <div className="flex h-full flex-col items-center justify-center text-sm text-(--secondary-text-wMain)">
                                    <File className="mx-auto mb-4 h-12 w-12" />
                                    No artifacts found matching your {searchQuery && selectedProject !== "all" ? "search and filter" : searchQuery ? "search" : "filter"}
                                </div>
                            )}

                            {/* Error state from fetching artifacts */}
                            {!isLoading && fetchError && (
                                <div className="flex h-full flex-col items-center justify-center text-sm text-(--secondary-text-wMain)">
                                    <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-(--error-wMain)" />
                                    <p className="text-(--error-wMain)">Failed to load artifacts</p>
                                    <p className="mt-2 text-xs">{fetchError?.message}</p>
                                    <Button variant="outline" className="mt-4" onClick={() => refetch()}>
                                        Try Again
                                    </Button>
                                </div>
                            )}

                            {!isLoading && !fetchError && artifacts.length === 0 && (
                                <div className="flex h-full flex-col items-center justify-center text-sm text-(--secondary-text-wMain)">
                                    <File className="mx-auto mb-4 h-12 w-12" />
                                    <p>No artifacts available</p>
                                    <p className="mt-2 text-xs">Upload files in chat or generate artifacts with AI</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Preview Panel */}
                {previewArtifact && (
                    <div className="w-1/2">
                        <StandalonePreviewPanel artifact={previewArtifact} onClose={handleClosePreview} onDownload={handleDownload} onGoToChat={handleGoToChat} onGoToProject={handleGoToProject} />
                    </div>
                )}
            </div>

            {/* Delete Confirmation Dialog */}
            <Dialog open={!!deleteConfirmArtifact} onOpenChange={open => !open && setDeleteConfirmArtifact(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete Artifact</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete <strong>{deleteConfirmArtifact?.filename}</strong>? This action cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteConfirmArtifact(null)}>
                            Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleDeleteConfirm}>
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
