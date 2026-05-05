import { memo, useCallback } from "react";
import { Download, FolderOpen, MessageCircle, X } from "lucide-react";

import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { type ArtifactWithSession, isProjectArtifact } from "@/lib/api/artifacts";
import { formatTimestamp } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";

import { FilePreviewBody } from "./FilePreviewBody";
import { ProjectBadge } from "./ProjectBadge";
import { useArtifactSource } from "./useFileAttachmentSource";

interface StandaloneArtifactPreviewProps {
    artifact: ArtifactWithSession;
    onClose: () => void;
    onDownload: (artifact: ArtifactWithSession) => void;
    onGoToChat: (artifact: ArtifactWithSession) => void;
    /** Optional — only relevant for project artifacts; the Go-to-Project button is hidden when omitted. */
    onGoToProject?: (artifact: ArtifactWithSession) => void;
}

/**
 * Self-contained artifact preview that fetches content directly from the API.
 * Works across sessions and projects — does not rely on ChatContext state.
 *
 * Body rendering and source state are shared with `LocalFilePreview` via
 * `FilePreviewBody` + `useArtifactSource`; this component owns header chrome
 * (project badge, version selector, navigation actions).
 */
export const StandaloneArtifactPreview = memo(function StandaloneArtifactPreview({ artifact, onClose, onDownload, onGoToChat, onGoToProject }: StandaloneArtifactPreviewProps) {
    const source = useArtifactSource(artifact);

    const handleVersionChange = useCallback(
        (version: string) => {
            source.setCurrentVersion(parseInt(version, 10));
        },
        [source]
    );

    const showGoToProject = isProjectArtifact(artifact) && !!onGoToProject && !!artifact.projectId;
    const showGoToChat = !isProjectArtifact(artifact);

    return (
        <div className="flex h-full flex-col">
            <div className="flex items-center gap-3 border-b px-3 py-2">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3 className="truncate text-sm font-semibold" title={artifact.filename}>
                            {artifact.filename}
                        </h3>
                        {artifact.projectName && <ProjectBadge text={artifact.projectName} className="flex-shrink-0" />}
                        {source.availableVersions.length > 1 && source.currentVersion !== null && (
                            <Select value={source.currentVersion.toString()} onValueChange={handleVersionChange}>
                                <SelectTrigger className="h-[16px] py-0 text-xs shadow-none">
                                    <SelectValue placeholder="Version" />
                                </SelectTrigger>
                                <SelectContent>
                                    {source.availableVersions.map(version => (
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

                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => onDownload(artifact)}>
                        <Download className="mr-1 h-4 w-4" />
                        Download
                    </Button>
                    {showGoToProject && (
                        <Button variant="ghost" size="sm" onClick={() => onGoToProject!(artifact)}>
                            <FolderOpen className="mr-1 h-4 w-4" />
                            Go to Project
                        </Button>
                    )}
                    {showGoToChat && (
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

            <FilePreviewBody
                fileContent={source.fileContent}
                isLoading={source.isLoading}
                error={source.error}
                setError={source.setError}
                canPreview={source.canPreview}
                rendererType={source.rendererType}
                mimeType={artifact.mime_type}
                filename={artifact.filename}
                onDownload={() => onDownload(artifact)}
            />
        </div>
    );
});
