import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { type ArtifactWithSession, isProjectArtifact } from "@/lib/api/artifacts";
import { canPreviewArtifact, getRenderType } from "@/lib/components/chat/preview/previewUtils";
import type { FileAttachment } from "@/lib/types";
import { getArtifactContent, getArtifactUrl } from "@/lib/utils";

const PREVIEW_CACHE_MS = 5 * 60 * 1000;

export interface FileAttachmentSourceState {
    fileContent: FileAttachment | null;
    isLoading: boolean;
    error: string | null;
    setError: (err: string | null) => void;
    canPreview: boolean;
    rendererType: ReturnType<typeof getRenderType>;
}

export interface ArtifactSourceState extends FileAttachmentSourceState {
    /** Empty until versions resolve; usually 1+ entries when populated. */
    availableVersions: number[];
    currentVersion: number | null;
    setCurrentVersion: (v: number) => void;
}

/**
 * Source state for a locally-selected `File` (not yet uploaded).
 * Reads bytes via FileReader and produces a `FileAttachment` ready for
 * `ContentRenderer`. Maintains an object URL for binary renderers (PDF, image).
 */
export function useLocalFileSource(file: File): FileAttachmentSourceState {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<FileAttachment | null>(null);

    const rendererType = useMemo(() => getRenderType(file.name, file.type), [file.name, file.type]);
    const canPreview = !!rendererType;

    // Object URL is recreated when the File identity changes; revoked on unmount.
    const blobUrl = useMemo(() => URL.createObjectURL(file), [file]);
    useEffect(() => () => URL.revokeObjectURL(blobUrl), [blobUrl]);

    useEffect(() => {
        if (!canPreview) {
            setIsLoading(false);
            return;
        }

        let cancelled = false;
        setIsLoading(true);
        setError(null);

        const reader = new FileReader();
        reader.onload = () => {
            if (cancelled) return;
            const result = reader.result as string;
            const commaIdx = result.indexOf(",");
            const base64 = commaIdx >= 0 ? result.substring(commaIdx + 1) : result;

            setFileContent({
                name: file.name,
                mime_type: file.type || "application/octet-stream",
                content: base64,
                last_modified: new Date(file.lastModified).toISOString(),
                size: file.size,
                url: blobUrl,
            });
            setIsLoading(false);
        };
        reader.onerror = () => {
            if (cancelled) return;
            setError("Failed to read file");
            setIsLoading(false);
        };
        reader.readAsDataURL(file);

        return () => {
            cancelled = true;
            reader.abort();
        };
    }, [file, blobUrl, canPreview]);

    return { fileContent, isLoading, error, setError, canPreview, rendererType };
}

/**
 * Source state for an existing artifact fetched from the API. Uses React Query
 * for the versions list and per-version content, with prefetching of adjacent
 * versions so switching is instant. Replaces the previous useRef<Map> cache.
 */
export function useArtifactSource(artifact: ArtifactWithSession): ArtifactSourceState {
    const queryClient = useQueryClient();
    const [renderError, setRenderError] = useState<string | null>(null);
    const [currentVersion, setCurrentVersion] = useState<number | null>(null);

    const projectId = isProjectArtifact(artifact) && artifact.projectId ? artifact.projectId : undefined;
    const sessionId = projectId ? undefined : artifact.sessionId;

    const preview = useMemo(() => canPreviewArtifact(artifact), [artifact]);
    const canPreview = !!preview?.canPreview;
    const rendererType = useMemo(() => getRenderType(artifact.filename, artifact.mime_type), [artifact.filename, artifact.mime_type]);

    // Reset the selected version whenever the artifact identity changes so a
    // version pinned for a previous file doesn't carry over to the next.
    useEffect(() => {
        setCurrentVersion(null);
        setRenderError(null);
    }, [artifact.filename, sessionId, projectId]);

    const versionsQuery = useQuery({
        queryKey: ["artifact-versions", projectId ?? null, sessionId ?? null, artifact.filename],
        queryFn: async (): Promise<number[]> => {
            const url = getArtifactUrl({ filename: artifact.filename, sessionId, projectId });
            const versions: number[] = await api.webui.get(url);
            // Newest first so the version dropdown shows the latest at the top.
            return [...(versions ?? [])].sort((a, b) => b - a);
        },
        enabled: canPreview,
        staleTime: PREVIEW_CACHE_MS,
    });

    // Memoise the empty fallback so dependent effects don't re-run when
    // `versionsQuery.data` is undefined (each render would otherwise produce a
    // fresh `[]` reference).
    const availableVersions = useMemo(() => versionsQuery.data ?? [], [versionsQuery.data]);

    // Once versions arrive, default to the latest. Re-applies after an artifact change.
    // (List is sorted descending, so [0] is the highest version.)
    useEffect(() => {
        if (currentVersion === null && availableVersions.length > 0) {
            setCurrentVersion(availableVersions[0]);
        }
    }, [availableVersions, currentVersion]);

    const contentQuery = useQuery({
        queryKey: ["artifact-content", projectId ?? null, sessionId ?? null, artifact.filename, currentVersion],
        queryFn: () => getArtifactContent({ filename: artifact.filename, sessionId, projectId, version: currentVersion ?? undefined }),
        enabled: canPreview && currentVersion !== null,
        staleTime: PREVIEW_CACHE_MS,
    });

    // Background prefetch the immediately-adjacent versions so version swaps
    // are instant (the previous implementation maintained this with useRef<Map>).
    useEffect(() => {
        if (currentVersion === null || availableVersions.length === 0) return;
        const idx = availableVersions.indexOf(currentVersion);
        const adjacent = [availableVersions[idx - 1], availableVersions[idx + 1]].filter((v): v is number => v !== undefined && v !== currentVersion);
        for (const v of adjacent) {
            queryClient.prefetchQuery({
                queryKey: ["artifact-content", projectId ?? null, sessionId ?? null, artifact.filename, v],
                queryFn: () => getArtifactContent({ filename: artifact.filename, sessionId, projectId, version: v }),
                staleTime: PREVIEW_CACHE_MS,
            });
        }
    }, [currentVersion, availableVersions, queryClient, artifact.filename, sessionId, projectId]);

    const fileContent: FileAttachment | null = useMemo(() => {
        if (!contentQuery.data || currentVersion === null) return null;
        const artifactUrl = getArtifactUrl({ filename: artifact.filename, sessionId, projectId, version: currentVersion });
        return {
            name: artifact.filename,
            mime_type: contentQuery.data.mimeType,
            content: contentQuery.data.content,
            last_modified: artifact.last_modified,
            url: api.webui.getFullUrl(artifactUrl),
        };
    }, [contentQuery.data, currentVersion, artifact.filename, artifact.last_modified, sessionId, projectId]);

    const fetchError = versionsQuery.error ?? contentQuery.error;
    const error = renderError ?? (fetchError instanceof Error ? fetchError.message : fetchError ? "Failed to load artifact" : null);
    const isLoading = canPreview && (versionsQuery.isLoading || (currentVersion !== null && contentQuery.isLoading));

    return {
        fileContent,
        isLoading,
        error,
        setError: setRenderError,
        canPreview,
        rendererType,
        availableVersions,
        currentVersion,
        setCurrentVersion,
    };
}
