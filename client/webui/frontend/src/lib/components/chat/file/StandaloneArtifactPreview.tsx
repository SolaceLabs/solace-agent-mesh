import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, File, FolderOpen, MessageCircle, X } from "lucide-react";

import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Spinner } from "@/lib/components/ui";
import { api } from "@/lib/api";
import { getArtifactContent, getArtifactUrl } from "@/lib/utils";
import { formatTimestamp } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { canPreviewArtifact, getFileContent, getRenderType } from "@/lib/components/chat/preview/previewUtils";
import type { FileAttachment } from "@/lib/types";
import type { ArtifactWithSession } from "@/lib/api/artifacts";

import { ProjectBadge } from "./ProjectBadge";

/**
 * True when the artifact belongs to a project rather than a chat session.
 * Backend uses "project-{id}" format; "project:{id}" is kept for backward compat.
 */
export function isProjectArtifact(artifact: ArtifactWithSession): boolean {
    return artifact.sessionId.startsWith("project:") || artifact.sessionId.startsWith("project-") || artifact.source === "project";
}

/**
 * Resolve the correct API path for an artifact.
 *
 * For project artifacts we pass "null" as the session placeholder in the path
 * and the actual project via the project_id query param — the backend endpoint
 * requires a session_id path segment.
 */
export function getArtifactApiUrl(artifact: ArtifactWithSession): string {
    if (isProjectArtifact(artifact) && artifact.projectId) {
        return `/api/v1/artifacts/null/${encodeURIComponent(artifact.filename)}?project_id=${encodeURIComponent(artifact.projectId)}`;
    }
    return `/api/v1/artifacts/${encodeURIComponent(artifact.sessionId)}/${encodeURIComponent(artifact.filename)}`;
}

interface StandaloneArtifactPreviewProps {
    artifact: ArtifactWithSession;
    onClose: () => void;
    onDownload: (artifact: ArtifactWithSession) => void;
    onGoToChat: (artifact: ArtifactWithSession) => void;
    onGoToProject: (artifact: ArtifactWithSession) => void;
}

/**
 * Self-contained artifact preview that fetches content directly from the API.
 * Works across sessions and projects — does not rely on ChatContext state.
 */
export const StandaloneArtifactPreview = memo(function StandaloneArtifactPreview({ artifact, onClose, onDownload, onGoToChat, onGoToProject }: StandaloneArtifactPreviewProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<FileAttachment | null>(null);
    const [availableVersions, setAvailableVersions] = useState<number[]>([]);
    const [currentVersion, setCurrentVersion] = useState<number | null>(null);

    // Cache of version number → FileAttachment so switching versions is instant
    const versionCache = useRef<Map<number, FileAttachment>>(new Map());

    const preview = useMemo(() => canPreviewArtifact(artifact), [artifact]);

    const sessionId = isProjectArtifact(artifact) ? undefined : artifact.sessionId;
    const projectId = isProjectArtifact(artifact) ? artifact.projectId : undefined;

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

    const fetchContentForVersion = useCallback(
        async (version: number | "latest") => {
            if (typeof version === "number" && versionCache.current.has(version)) {
                setFileContent(versionCache.current.get(version)!);
                return;
            }

            setIsLoading(true);
            setError(null);

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
                const versionsUrl = getArtifactUrl({ filename: artifact.filename, sessionId, projectId });
                const versions: number[] = await api.webui.get(versionsUrl);

                if (!isMounted) return;

                if (versions && versions.length > 0) {
                    const sortedVersions = versions.sort((a, b) => a - b);
                    const latestVersion = Math.max(...sortedVersions);
                    setAvailableVersions(sortedVersions);
                    setCurrentVersion(latestVersion);

                    const { content, mimeType } = await getArtifactContent({ filename: artifact.filename, sessionId, projectId, version: latestVersion });
                    if (!isMounted) return;

                    const file = buildFileAttachment(content, mimeType, latestVersion);
                    versionCache.current.set(latestVersion, file);
                    setFileContent(file);

                    // Pre-fetch adjacent versions so switching is instant.
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

    const handleVersionChange = useCallback(
        async (version: string) => {
            const versionNum = parseInt(version, 10);
            setCurrentVersion(versionNum);
            await fetchContentForVersion(versionNum);
        },
        [fetchContentForVersion]
    );

    const rendererType = useMemo(() => getRenderType(artifact.filename, artifact.mime_type), [artifact.filename, artifact.mime_type]);
    const content = useMemo(() => getFileContent(fileContent), [fileContent]);
    const effectiveUrl = fileContent?.url;

    const memoizedContentRenderer = useMemo(() => {
        if (!preview?.canPreview || !rendererType || !content) return null;
        return <ContentRenderer content={content} rendererType={rendererType} mime_type={artifact.mime_type} url={effectiveUrl} filename={artifact.filename} setRenderError={setError} />;
    }, [content, rendererType, artifact.mime_type, effectiveUrl, artifact.filename, preview?.canPreview]);

    return (
        <div className="flex h-full flex-col border-l">
            <div className="flex items-center gap-3 border-b px-3 py-2">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h3 className="truncate text-sm font-semibold" title={artifact.filename}>
                            {artifact.filename}
                        </h3>
                        {artifact.projectName && <ProjectBadge text={artifact.projectName} className="flex-shrink-0" />}
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

            <div className="min-h-0 flex-1 overflow-auto">
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
