import React, { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Download, Trash2, FileText, FileImage, FileCode, File, FileSpreadsheet, FileArchive, MoreHorizontal, MessageCircle } from "lucide-react";
import { Button, Input, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, Spinner } from "@/lib/components/ui";
import { useAllArtifacts, useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";

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
}

/**
 * Get the appropriate icon for a file based on its MIME type
 */
const getFileIcon = (mimeType: string) => {
    if (mimeType.startsWith("image/")) {
        return FileImage;
    }
    if (mimeType.startsWith("text/") || mimeType.includes("json") || mimeType.includes("xml")) {
        return FileCode;
    }
    if (mimeType.includes("spreadsheet") || mimeType.includes("excel") || mimeType.includes("csv")) {
        return FileSpreadsheet;
    }
    if (mimeType.includes("zip") || mimeType.includes("tar") || mimeType.includes("gzip") || mimeType.includes("compressed")) {
        return FileArchive;
    }
    if (mimeType.includes("pdf") || mimeType.includes("document") || mimeType.includes("word")) {
        return FileText;
    }
    return File;
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

interface ArtifactCardProps {
    artifact: ArtifactWithSession;
    onDownload: (artifact: ArtifactWithSession) => void;
    onDelete: (artifact: ArtifactWithSession) => void;
    onPreview: (artifact: ArtifactWithSession) => void;
    onGoToChat: (artifact: ArtifactWithSession) => void;
}

const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact, onDownload, onDelete, onPreview, onGoToChat }) => {
    const IconComponent = getFileIcon(artifact.mime_type);
    const origin = getArtifactOrigin(artifact);

    return (
        <div className="hover:bg-accent/50 flex items-center gap-3 rounded-md border p-3 shadow-sm transition-colors">
            <button onClick={() => onPreview(artifact)} className="min-w-0 flex-1 cursor-pointer text-left">
                <div className="flex items-center gap-3">
                    <div className="bg-muted flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md">
                        <IconComponent className="text-muted-foreground h-5 w-5" />
                    </div>
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                        <div className="flex items-center gap-2">
                            <span className="truncate font-semibold">{artifact.filename}</span>
                            {origin && <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${origin.color}`}>{origin.label}</span>}
                        </div>
                        <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
                            <span>{formatFileSize(artifact.size)}</span>
                            <span>•</span>
                            <span>{formatTimestamp(artifact.last_modified)}</span>
                        </div>
                    </div>
                </div>
            </button>
            <div className="flex flex-shrink-0 items-center">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={e => e.stopPropagation()}>
                            <MoreHorizontal size={16} />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                onGoToChat(artifact);
                            }}
                        >
                            <MessageCircle size={16} className="mr-2" />
                            Go to Chat
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                onDownload(artifact);
                            }}
                        >
                            <Download size={16} className="mr-2" />
                            Download
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                onDelete(artifact);
                            }}
                            className="text-red-600 focus:text-red-600 dark:text-red-500 dark:focus:text-red-500"
                        >
                            <Trash2 size={16} className="mr-2" />
                            Delete
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    );
};

export const ArtifactsPage: React.FC = () => {
    const navigate = useNavigate();
    const { addNotification, displayError, handleSwitchSession } = useChatContext();
    const { artifacts, isLoading, refetch } = useAllArtifacts();
    const [searchQuery, setSearchQuery] = useState<string>("");

    // Filter artifacts by search query
    const filteredArtifacts = useMemo(() => {
        if (!searchQuery.trim()) {
            return artifacts;
        }
        const query = searchQuery.toLowerCase().trim();
        return artifacts.filter(artifact => {
            const filename = artifact.filename.toLowerCase();
            const mimeType = artifact.mime_type.toLowerCase();
            const sessionName = artifact.sessionName?.toLowerCase() || "";
            return filename.includes(query) || mimeType.includes(query) || sessionName.includes(query);
        });
    }, [artifacts, searchQuery]);

    const handleDownload = useCallback(
        async (artifact: ArtifactWithSession) => {
            try {
                // Fetch the artifact content using full response
                const response = await api.webui.get(`/api/v1/artifacts/${artifact.sessionId}/${encodeURIComponent(artifact.filename)}`, { fullResponse: true });
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
            // Switch to the artifact's session first, then navigate
            await handleSwitchSession(artifact.sessionId);
            navigate("/chat");
            // Dispatch event to open artifact preview after a short delay to allow navigation to complete
            if (typeof window !== "undefined") {
                setTimeout(() => {
                    window.dispatchEvent(
                        new CustomEvent("open-artifact-preview", {
                            detail: { artifact },
                        })
                    );
                }, 100);
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

    return (
        <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b px-6 py-4">
                <div>
                    <h1 className="text-foreground text-xl font-semibold">Artifacts</h1>
                    <p className="text-muted-foreground mt-1 text-sm">View and manage all your files and artifacts across all chat sessions</p>
                </div>
            </div>

            <div className="flex h-full flex-col gap-4 py-6 pl-6">
                {/* Search Input */}
                <div className="flex items-center gap-4 pr-4">
                    <div className="relative w-64">
                        <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                        <Input type="text" placeholder="Search artifacts..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="pl-9" />
                    </div>
                    {!isLoading && artifacts.length > 0 && (
                        <span className="text-muted-foreground text-sm">
                            {artifacts.length} artifact{artifacts.length !== 1 ? "s" : ""}
                        </span>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto">
                    {isLoading && (
                        <div className="flex h-full items-center justify-center">
                            <Spinner size="large" variant="muted" />
                        </div>
                    )}

                    {!isLoading && filteredArtifacts.length > 0 && (
                        <ul className="space-y-2">
                            {filteredArtifacts.map(artifact => (
                                <li key={`${artifact.sessionId}-${artifact.filename}-${artifact.version || 0}`} className="pr-4">
                                    <ArtifactCard artifact={artifact} onDownload={handleDownload} onDelete={handleDelete} onPreview={handlePreview} onGoToChat={handleGoToChat} />
                                </li>
                            ))}
                        </ul>
                    )}

                    {!isLoading && filteredArtifacts.length === 0 && artifacts.length > 0 && (
                        <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                            <File className="mx-auto mb-4 h-12 w-12" />
                            No artifacts found matching your search
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
