import React, { useState, useMemo, useCallback, useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Download, Trash2, File, MoreHorizontal, MessageCircle, Eye, FileImage, FileCode, FileText, Presentation, FolderOpen } from "lucide-react";
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
} from "@/lib/components/ui";
import { useAllArtifacts, useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api";
import { formatTimestamp, cn } from "@/lib/utils";
import { DocumentThumbnail, supportsThumbnail } from "@/lib/components/chat/file/DocumentThumbnail";
import { ProjectBadge } from "@/lib/components/chat/file/ProjectBadge";
import { ConfigContext } from "@/lib/contexts/ConfigContext";

// Cache for document content to avoid re-fetching on subsequent renders
const documentContentCache = new Map<string, string>();

// Generate cache key for document content
const getDocumentCacheKey = (sessionId: string, filename: string): string => {
    return `${sessionId}:${filename}`;
};

// Extended artifact type with session info
interface ArtifactWithSession {
    filename: string;
    mime_type: string;
    size: number;
    last_modified: string;
    uri?: string;
    version?: number;
    versionCount?: number;
    description?: string | null;
    source?: string;
    sessionId: string;
    sessionName: string | null;
    projectId?: string;
    projectName?: string | null;
}

// Helper to check if artifact is a project artifact
const isProjectArtifact = (artifact: ArtifactWithSession): boolean => {
    return artifact.sessionId.startsWith("project:") || artifact.source === "project";
};

// Helper to get the correct API URL for an artifact
const getArtifactApiUrl = (artifact: ArtifactWithSession): string => {
    if (isProjectArtifact(artifact) && artifact.projectId) {
        // Project artifacts use the artifacts endpoint with project_id query param
        return `/api/v1/artifacts/null/${encodeURIComponent(artifact.filename)}?project_id=${encodeURIComponent(artifact.projectId)}`;
    }
    return `/api/v1/artifacts/${artifact.sessionId}/${encodeURIComponent(artifact.filename)}`;
};

/**
 * Format file size in human-readable format
 */
const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

/**
 * Determine if an artifact was uploaded or generated based on source and mime type
 * Returns null if we can't determine the origin (to hide the badge)
 */
const getArtifactOrigin = (artifact: ArtifactWithSession): { label: string; color: string } | null => {
    // Check the source field first - only show badge if we have explicit source info
    if (artifact.source === "upload" || artifact.source === "user" || artifact.source === "uploaded") {
        return { label: "Uploaded", color: "bg-blue-500/20 text-blue-600 dark:text-blue-400" };
    }
    if (artifact.source === "generated" || artifact.source === "agent" || artifact.source === "ai") {
        return { label: "Generated", color: "bg-green-500/20 text-green-600 dark:text-green-400" };
    }
    if (artifact.source === "project") {
        return { label: "Project", color: "bg-purple-500/20 text-purple-600 dark:text-purple-400" };
    }

    // If no explicit source, return null to hide the badge
    return null;
};

/**
 * Get file extension from filename
 */
const getFileExtension = (filename: string): string => {
    const parts = filename.split(".");
    return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
};

/**
 * Get colorful badge style based on file extension/mime type
 */
const getExtensionBadgeStyle = (filename: string): string => {
    const ext = getFileExtension(filename).toLowerCase();

    // Color mapping based on file type
    switch (ext) {
        case "html":
        case "htm":
            return "bg-[#e34c26] text-white";
        case "json":
            return "bg-[#fbc02d] text-[#333]";
        case "yaml":
        case "yml":
            return "bg-[#cb171e] text-white";
        case "md":
        case "markdown":
            return "bg-[#6c757d] text-white";
        case "txt":
            return "bg-[#5c6bc0] text-white";
        case "js":
        case "jsx":
            return "bg-[#f7df1e] text-[#333]";
        case "ts":
        case "tsx":
            return "bg-[#3178c6] text-white";
        case "py":
            return "bg-[#3776ab] text-white";
        case "css":
            return "bg-[#264de4] text-white";
        case "scss":
        case "sass":
            return "bg-[#cc6699] text-white";
        case "xml":
            return "bg-[#f16529] text-white";
        case "pdf":
            return "bg-[#ff0000] text-white";
        case "doc":
        case "docx":
            return "bg-[#2b579a] text-white";
        case "xls":
        case "xlsx":
        case "csv":
            return "bg-[#217346] text-white";
        case "ppt":
        case "pptx":
            return "bg-[#d24726] text-white";
        case "zip":
        case "rar":
        case "7z":
        case "tar":
        case "gz":
            return "bg-[#f9a825] text-[#333]";
        case "jpg":
        case "jpeg":
        case "png":
        case "gif":
        case "svg":
        case "webp":
            return "bg-[#4caf50] text-white";
        case "mp4":
        case "avi":
        case "mov":
        case "webm":
            return "bg-[#9c27b0] text-white";
        case "mp3":
        case "wav":
        case "flac":
            return "bg-[#ff5722] text-white";
        default:
            return "bg-gray-500 text-white";
    }
};

/**
 * Check if a MIME type supports text preview
 */
const supportsTextPreview = (mimeType: string): boolean => {
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
};

/**
 * Check if a MIME type is an image
 */
const isImageType = (mimeType: string): boolean => {
    return mimeType.startsWith("image/");
};

interface ArtifactGridCardProps {
    artifact: ArtifactWithSession;
    onDownload: (artifact: ArtifactWithSession) => void;
    onDelete: (artifact: ArtifactWithSession) => void;
    onPreview: (artifact: ArtifactWithSession) => void;
    onGoToChat: (artifact: ArtifactWithSession) => void;
    onGoToProject: (artifact: ArtifactWithSession) => void;
    isSelected?: boolean;
}

const ArtifactGridCard: React.FC<ArtifactGridCardProps> = ({ artifact, onDownload, onDelete, onPreview, onGoToChat, onGoToProject, isSelected }) => {
    const origin = getArtifactOrigin(artifact);
    const config = useContext(ConfigContext);
    const [contentPreview, setContentPreview] = useState<string | null>(null);
    const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
    const [documentContent, setDocumentContent] = useState<string | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);
    const [documentThumbnailFailed, setDocumentThumbnailFailed] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);

    // Check if this file supports document thumbnail
    const isDocumentThumbnailSupported = supportsThumbnail(artifact.filename, artifact.mime_type);
    const binaryArtifactPreviewEnabled = config?.binaryArtifactPreviewEnabled ?? false;

    // Check if file is a PDF (doesn't need conversion service)
    const isPdfFile = artifact.mime_type === "application/pdf" || artifact.filename.toLowerCase().endsWith(".pdf");

    // Only enable document thumbnail if: it's a PDF (always works) OR it's an Office doc and conversion is enabled
    const canAttemptDocumentThumbnail = isDocumentThumbnailSupported && (isPdfFile || binaryArtifactPreviewEnabled);

    // Load content preview for text files, image thumbnail, or document thumbnail
    useEffect(() => {
        const loadPreview = async () => {
            // Get the correct API URL for this artifact (handles both session and project artifacts)
            const artifactApiUrl = getArtifactApiUrl(artifact);

            if (isImageType(artifact.mime_type)) {
                // For images, create a thumbnail URL
                try {
                    const url = api.webui.getFullUrl(artifactApiUrl);
                    setImagePreviewUrl(url);
                } catch (error) {
                    console.error("Error creating image preview URL:", error);
                }
            } else if (canAttemptDocumentThumbnail && !documentThumbnailFailed) {
                // For PDF, DOCX, PPTX, etc. - check cache first, then fetch content for thumbnail
                const cacheKey = getDocumentCacheKey(artifact.sessionId, artifact.filename);
                const cachedContent = documentContentCache.get(cacheKey);

                if (cachedContent) {
                    // Use cached content
                    setDocumentContent(cachedContent);
                    return;
                }

                setIsLoadingPreview(true);
                try {
                    const response = await api.webui.get(artifactApiUrl, { fullResponse: true });
                    const blob = await response.blob();
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
                    // Cache the content for future renders
                    documentContentCache.set(cacheKey, base64data);
                    setDocumentContent(base64data);
                } catch (error) {
                    console.error("Error loading document content for thumbnail:", error);
                    setDocumentContent(null);
                } finally {
                    setIsLoadingPreview(false);
                }
            } else if (supportsTextPreview(artifact.mime_type) && artifact.size < 50000) {
                // Only load preview for text files under 50KB
                setIsLoadingPreview(true);
                try {
                    const response = await api.webui.get(artifactApiUrl, { fullResponse: true });
                    const text = await response.text();
                    // Get first 8 lines for preview (increased from 4), max 60 chars per line
                    const lines = text.split("\n").slice(0, 8);
                    const preview = lines
                        .map(line => {
                            const trimmed = line.trim();
                            return trimmed.length > 60 ? trimmed.substring(0, 57) + "..." : trimmed;
                        })
                        .join("\n");
                    setContentPreview(preview);
                } catch (error) {
                    console.error("Error loading content preview:", error);
                    setContentPreview(null);
                } finally {
                    setIsLoadingPreview(false);
                }
            }
        };

        loadPreview();
    }, [artifact.sessionId, artifact.filename, artifact.mime_type, artifact.size, artifact.projectId, canAttemptDocumentThumbnail, documentThumbnailFailed]);

    // Handle document thumbnail error - fall back to icon
    const handleDocumentThumbnailError = useCallback(() => {
        setDocumentThumbnailFailed(true);
    }, []);

    // Check if we can show document thumbnail
    const canShowDocumentThumbnail = canAttemptDocumentThumbnail && documentContent && !documentThumbnailFailed;

    const handleCardClick = () => {
        onPreview(artifact);
    };

    return (
        <Card
            className={cn(
                "group relative flex h-[220px] w-[280px] flex-shrink-0 cursor-pointer flex-col gap-0 overflow-hidden transition-all",
                "hover:bg-[var(--color-primary-w10)] dark:hover:bg-[var(--color-primary-wMain)]",
                "focus-visible:border-[var(--color-brand-w100)] focus-visible:outline-none",
                isSelected && "border-[var(--color-brand-w100)]"
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
                    <span className="text-muted-foreground text-xs">{formatFileSize(artifact.size)}</span>
                    <span className="text-muted-foreground text-xs">•</span>
                    <span className="text-muted-foreground text-xs">{formatTimestamp(artifact.last_modified)}</span>
                    {/* Only show origin badge for non-project artifacts (project badge is shown in header) */}
                    {origin && origin.label !== "Project" && <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${origin.color}`}>{origin.label}</span>}
                </div>
                {/* Extension badge */}
                <span className={cn("rounded px-2 py-0.5 text-[10px] font-bold", getExtensionBadgeStyle(artifact.filename))}>
                    {getFileExtension(artifact.filename).length > 4 ? getFileExtension(artifact.filename).substring(0, 4) : getFileExtension(artifact.filename)}
                </span>
            </div>
        </Card>
    );
};

export const ArtifactsPage: React.FC = () => {
    const navigate = useNavigate();
    const { addNotification, displayError, handleSwitchSession } = useChatContext();
    const { artifacts, isLoading, refetch } = useAllArtifacts();
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedProject, setSelectedProject] = useState<string>("all");

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

    const handleDelete = useCallback(
        async (artifact: ArtifactWithSession) => {
            // Don't allow deleting project artifacts from here
            if (isProjectArtifact(artifact)) {
                displayError?.({
                    title: "Cannot Delete",
                    error: "Project artifacts must be deleted from the project page",
                });
                return;
            }
            try {
                await api.webui.delete(`/api/v1/artifacts/${artifact.sessionId}/${encodeURIComponent(artifact.filename)}`);
                addNotification?.(`Deleted ${artifact.filename}`, "success");
                refetch();
            } catch (error) {
                console.error("Error deleting artifact:", error);
                displayError?.({
                    title: "Delete Failed",
                    error: error instanceof Error ? error.message : "Failed to delete artifact",
                });
            }
        },
        [addNotification, displayError, refetch]
    );

    const handlePreview = useCallback(
        async (artifact: ArtifactWithSession) => {
            // For project artifacts, navigate to the project page instead
            if (isProjectArtifact(artifact) && artifact.projectId) {
                navigate(`/projects/${artifact.projectId}`);
                return;
            }

            // Switch to the artifact's session first, then navigate
            await handleSwitchSession(artifact.sessionId);
            navigate("/chat");

            // Robust event-driven coordination:
            // 1. Set up a one-time listener for session-loaded event
            // 2. Dispatch the preview request with the artifact data
            // 3. ChatProvider will emit session-loaded when ready, then we open preview
            // 4. Fallback timeout ensures we don't wait forever
            if (typeof window !== "undefined") {
                const timeoutMs = 3000; // Max wait time
                let resolved = false;

                const openPreviewNow = () => {
                    if (resolved) return;
                    resolved = true;
                    window.dispatchEvent(
                        new CustomEvent("open-artifact-preview", {
                            detail: { artifact },
                        })
                    );
                };

                // Listen for session-loaded event (emitted by ChatProvider after loadSessionTasks)
                const handleSessionLoaded = (event: Event) => {
                    const customEvent = event as CustomEvent;
                    if (customEvent.detail?.sessionId === artifact.sessionId) {
                        window.removeEventListener("session-loaded", handleSessionLoaded);
                        openPreviewNow();
                    }
                };

                window.addEventListener("session-loaded", handleSessionLoaded);

                // Fallback: if session-loaded doesn't fire within timeout, try anyway
                setTimeout(() => {
                    window.removeEventListener("session-loaded", handleSessionLoaded);
                    openPreviewNow();
                }, timeoutMs);
            }
        },
        [navigate, handleSwitchSession]
    );

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
            <div className="flex items-center justify-between border-b px-6 py-4">
                <div>
                    <h1 className="text-foreground text-xl font-semibold">Artifacts</h1>
                    <p className="text-muted-foreground mt-1 text-sm">View and manage all your files and artifacts across chat sessions and projects</p>
                </div>
            </div>

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
                                    onDelete={handleDelete}
                                    onPreview={handlePreview}
                                    onGoToChat={handleGoToChat}
                                    onGoToProject={handleGoToProject}
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

                    {!isLoading && artifacts.length === 0 && (
                        <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                            <File className="mx-auto mb-4 h-12 w-12" />
                            <p>No artifacts available</p>
                            <p className="mt-2 text-xs">Upload files in chat or generate artifacts with AI</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
