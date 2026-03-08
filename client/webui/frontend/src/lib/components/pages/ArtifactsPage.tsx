import { useState, useMemo, useCallback, useEffect, useContext, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Download, Trash2, File, MoreHorizontal, MessageCircle, Eye, FileImage, FileCode, FileText, Presentation, FolderOpen, X, AlertTriangle } from "lucide-react";
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
import { useAllArtifacts, useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api";
import { formatTimestamp, cn, createLruCache } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";
import { DocumentThumbnail, supportsThumbnail } from "@/lib/components/chat/file/DocumentThumbnail";
import { ProjectBadge } from "@/lib/components/chat/file/ProjectBadge";
import { getFileTypeColor } from "@/lib/components/chat/file/FileIcon";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { canPreviewArtifact, getFileContent, getRenderType } from "@/lib/components/chat/preview/previewUtils";
import { Header } from "@/lib/components/header/Header";
import type { FileAttachment } from "@/lib/types";
import type { ArtifactWithSession } from "@/lib/hooks/useAllArtifacts";

// LRU Cache for document content with max size to prevent memory leaks
const documentContentCache = createLruCache<string>(50);

// Generate cache key for document content
function getDocumentCacheKey(sessionId: string, filename: string): string {
    return `${sessionId}:${filename}`;
}

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

function ArtifactGridCard({ artifact, onDownload, onDelete, onPreview, onGoToChat, onGoToProject, isSelected, binaryArtifactPreviewEnabled }: ArtifactGridCardProps) {
    const [contentPreview, setContentPreview] = useState<string | null>(null);
    const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
    const [documentContent, setDocumentContent] = useState<string | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);
    const [documentThumbnailFailed, setDocumentThumbnailFailed] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);

    // Check if this file supports document thumbnail
    const isDocumentThumbnailSupported = supportsThumbnail(artifact.filename, artifact.mime_type);

    // Check if file is a PDF (doesn't need conversion service)
    const isPdfFile = artifact.mime_type === "application/pdf" || artifact.filename.toLowerCase().endsWith(".pdf");

    // Only enable document thumbnail if: it's a PDF (always works) OR it's an Office doc and conversion is enabled
    const canAttemptDocumentThumbnail = isDocumentThumbnailSupported && (isPdfFile || binaryArtifactPreviewEnabled);

    // Load content preview for text files, image thumbnail, or document thumbnail
    useEffect(() => {
        // Track if component is still mounted
        let isMounted = true;
        const abortController = new AbortController();

        const loadPreview = async () => {
            // Get the correct API URL for this artifact (handles both session and project artifacts)
            const artifactApiUrl = getArtifactApiUrl(artifact);

            if (isImageType(artifact.mime_type)) {
                // For images, create a thumbnail URL
                try {
                    const url = api.webui.getFullUrl(artifactApiUrl);
                    if (isMounted) setImagePreviewUrl(url);
                } catch (error) {
                    console.error("Error creating image preview URL:", error);
                }
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
                try {
                    const response = await api.webui.get(artifactApiUrl, { fullResponse: true });
                    if (abortController.signal.aborted) return;

                    const blob = await response.blob();
                    if (abortController.signal.aborted) return;

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
                // For text files, fetch a preview of the content
                if (isMounted) setIsLoadingPreview(true);
                try {
                    const response = await api.webui.get(artifactApiUrl, { fullResponse: true });
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

                    if (isMounted) {
                        setContentPreview(preview);
                        setIsLoadingPreview(false);
                    }
                } catch (error) {
                    if (!abortController.signal.aborted) {
                        console.error("Error loading text preview:", error);
                        if (isMounted) setIsLoadingPreview(false);
                    }
                }
            }
        };

        loadPreview();

        return () => {
            isMounted = false;
            abortController.abort();
        };
    }, [artifact.sessionId, artifact.filename, artifact.mime_type, artifact.projectId, canAttemptDocumentThumbnail]);

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
                "group relative flex h-[220px] w-[280px] flex-shrink-0 cursor-pointer flex-col gap-0 overflow-hidden transition-all",
                "hover:bg-(--color-primary-w10) dark:hover:bg-(--color-primary-wMain)",
                "focus-visible:border-(--color-brand-w100) focus-visible:outline-none",
                isSelected && "border-(--color-brand-w100)"
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
            <div className="bg-muted/30 relative flex flex-1 items-center justify-center overflow-hidden">
                {imagePreviewUrl ? (
                    <img src={imagePreviewUrl} alt={artifact.filename} className="h-full w-full object-cover" onError={() => setImagePreviewUrl(null)} />
                ) : canShowDocumentThumbnail && documentContent ? (
                    <DocumentThumbnail content={documentContent} filename={artifact.filename} mimeType={artifact.mime_type} width={280} height={130} onError={handleDocumentThumbnailError} className="absolute inset-0 h-full w-full" />
                ) : contentPreview ? (
                    <div className="text-muted-foreground h-full w-full overflow-hidden px-3 py-2 font-mono text-[11px] leading-relaxed">
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
                            <FileImage className="text-muted-foreground h-12 w-12" />
                        ) : supportsTextPreview(artifact.mime_type) ? (
                            <FileCode className="text-muted-foreground h-12 w-12" />
                        ) : isDocumentThumbnailSupported ? (
                            // Show appropriate icon for document types while loading or if thumbnail failed
                            artifact.mime_type.includes("pdf") ? (
                                <FileText className="text-muted-foreground h-12 w-12" />
                            ) : artifact.mime_type.includes("presentation") || artifact.filename.toLowerCase().endsWith(".pptx") || artifact.filename.toLowerCase().endsWith(".ppt") ? (
                                <Presentation className="text-muted-foreground h-12 w-12" />
                            ) : (
                                <FileText className="text-muted-foreground h-12 w-12" />
                            )
                        ) : (
                            <File className="text-muted-foreground h-12 w-12" />
                        )}
                        {artifact.description && <span className="text-muted-foreground px-4 text-center text-xs">{artifact.description}</span>}
                    </div>
                )}

                {/* Hover overlay with preview button */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
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
                    <span className="text-muted-foreground text-xs">{formatBytes(artifact.size)}</span>
                    <span className="text-muted-foreground text-xs">•</span>
                    <span className="text-muted-foreground text-xs">{formatTimestamp(artifact.last_modified)}</span>
                </div>
                {/* Extension badge - uses shared getFileTypeColor from FileIcon */}
                <span className={cn("rounded px-2 py-0.5 text-[10px] font-bold text-white", getFileTypeColor(artifact.mime_type, artifact.filename))}>
                    {getFileExtension(artifact.filename).length > 4 ? getFileExtension(artifact.filename).substring(0, 4) : getFileExtension(artifact.filename)}
                </span>
            </div>
        </Card>
    );
}

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

function StandalonePreviewPanel({ artifact, onClose, onDownload, onGoToChat, onGoToProject }: StandalonePreviewPanelProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<FileAttachment | null>(null);
    const lastFetchedRef = useRef<string | null>(null);

    // Check if preview is supported
    const preview = useMemo(() => canPreviewArtifact(artifact), [artifact]);

    // Fetch artifact content
    useEffect(() => {
        // Create a unique key for this artifact
        const artifactKey = `${artifact.sessionId}:${artifact.filename}:${artifact.projectId || ""}`;

        // Prevent duplicate fetches for the same artifact
        if (lastFetchedRef.current === artifactKey) {
            return;
        }

        async function fetchContent() {
            lastFetchedRef.current = artifactKey;
            setIsLoading(true);
            setError(null);

            try {
                const apiUrl = getArtifactApiUrl(artifact);
                const response = await api.webui.get(apiUrl, { fullResponse: true });
                const blob = await response.blob();

                // Convert blob to base64
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

                // Create file attachment object
                const file: FileAttachment = {
                    name: artifact.filename,
                    mime_type: artifact.mime_type,
                    content: base64data,
                    last_modified: artifact.last_modified,
                    url: api.webui.getFullUrl(apiUrl),
                };

                setFileContent(file);
            } catch (err) {
                console.error("Error fetching artifact content:", err);
                setError(err instanceof Error ? err.message : "Failed to load artifact content");
            } finally {
                setIsLoading(false);
            }
        }

        if (preview?.canPreview) {
            fetchContent();
        } else {
            setIsLoading(false);
        }
    }, [artifact.filename, artifact.sessionId, artifact.projectId, artifact.mime_type, artifact.last_modified, preview]);

    // Get renderer type and content
    const rendererType = getRenderType(artifact.filename, artifact.mime_type);
    const content = getFileContent(fileContent);
    const effectiveUrl = fileContent?.url;

    return (
        <div className="flex h-full flex-col border-l">
            {/* Compact Header - filename, metadata, actions, and close button in one bar */}
            <div className="flex items-center gap-3 border-b px-3 py-2">
                {/* Left side: filename and metadata */}
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3 className="truncate text-sm font-semibold" title={artifact.filename}>
                            {artifact.filename}
                        </h3>
                        {artifact.projectName && <ProjectBadge text={artifact.projectName} className="flex-shrink-0" />}
                    </div>
                    <div className="text-muted-foreground mt-0.5 flex items-center gap-2 text-xs">
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
                {isLoading && (
                    <div className="flex h-full items-center justify-center">
                        <Spinner size="medium" variant="muted" />
                    </div>
                )}

                {error && (
                    <div className="flex h-full flex-col items-center justify-center p-4">
                        <div className="text-destructive mb-2 text-sm">Error loading preview</div>
                        <div className="text-muted-foreground text-xs">{error}</div>
                    </div>
                )}

                {!isLoading && !error && !preview?.canPreview && (
                    <div className="flex h-full flex-col items-center justify-center p-4">
                        <File className="text-muted-foreground mb-4 h-12 w-12" />
                        <div className="text-muted-foreground text-sm">{preview?.reason || "Preview not available"}</div>
                        <Button variant="default" className="mt-4" onClick={() => onDownload(artifact)}>
                            <Download className="mr-2 h-4 w-4" />
                            Download File
                        </Button>
                    </div>
                )}

                {!isLoading && !error && preview?.canPreview && rendererType && content && (
                    <div className="h-full w-full">
                        <ContentRenderer content={content} rendererType={rendererType} mime_type={artifact.mime_type} url={effectiveUrl} filename={artifact.filename} setRenderError={setError} />
                    </div>
                )}
            </div>
        </div>
    );
}

export function ArtifactsPage() {
    const navigate = useNavigate();
    const { addNotification, displayError, handleSwitchSession } = useChatContext();
    const { artifacts, isLoading, error: fetchError, refetch } = useAllArtifacts();
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedProject, setSelectedProject] = useState<string>("all");
    const [previewArtifact, setPreviewArtifact] = useState<ArtifactWithSession | null>(null);
    const [deleteConfirmArtifact, setDeleteConfirmArtifact] = useState<ArtifactWithSession | null>(null);

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

    // Filter artifacts by project and search query
    const filteredArtifacts = useMemo(() => {
        let filtered = artifacts;

        // Filter by project
        if (selectedProject !== "all") {
            if (selectedProject === "(No Project)") {
                filtered = filtered.filter(artifact => !artifact.projectName);
            } else {
                filtered = filtered.filter(artifact => artifact.projectName === selectedProject);
            }
        }

        // Filter by search query
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase().trim();
            filtered = filtered.filter(artifact => {
                const filename = artifact.filename.toLowerCase();
                const mimeType = artifact.mime_type.toLowerCase();
                const sessionName = artifact.sessionName?.toLowerCase() || "";
                const projectName = artifact.projectName?.toLowerCase() || "";
                return filename.includes(query) || mimeType.includes(query) || sessionName.includes(query) || projectName.includes(query);
            });
        }

        return filtered;
    }, [artifacts, selectedProject, searchQuery]);

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
            <Header title="Artifacts" />

            {/* Content area with optional preview panel */}
            <div className="flex min-h-0 flex-1">
                {/* Main content area */}
                <div className={cn("flex min-h-0 flex-col transition-all", previewArtifact ? "w-1/2" : "w-full")}>
                    <div className="flex h-full flex-col gap-4 py-6 pl-6">
                        {/* Search and Project Filter on same line */}
                        <div className="flex items-center gap-4 pr-4">
                            {/* Search Input */}
                            <div className="relative w-64">
                                <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
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

                            {!isLoading && artifacts.length > 0 && (
                                <span className="text-muted-foreground text-sm">
                                    {filteredArtifacts.length} artifact{filteredArtifacts.length !== 1 ? "s" : ""}
                                    {(searchQuery || selectedProject !== "all") && filteredArtifacts.length !== artifacts.length && ` (of ${artifacts.length})`}
                                </span>
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
                                <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                                    <File className="mx-auto mb-4 h-12 w-12" />
                                    No artifacts found matching your {searchQuery && selectedProject !== "all" ? "search and filter" : searchQuery ? "search" : "filter"}
                                </div>
                            )}

                            {/* Error state from fetching artifacts */}
                            {!isLoading && fetchError && (
                                <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                                    <AlertTriangle className="text-destructive mx-auto mb-4 h-12 w-12" />
                                    <p className="text-destructive">Failed to load artifacts</p>
                                    <p className="mt-2 text-xs">{fetchError}</p>
                                    <Button variant="outline" className="mt-4" onClick={() => refetch()}>
                                        Try Again
                                    </Button>
                                </div>
                            )}

                            {!isLoading && !fetchError && artifacts.length === 0 && (
                                <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
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
                        <StandalonePreviewPanel artifact={previewArtifact} onClose={() => setPreviewArtifact(null)} onDownload={handleDownload} onGoToChat={handleGoToChat} onGoToProject={handleGoToProject} />
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
