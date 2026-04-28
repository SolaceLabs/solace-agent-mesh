import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Spinner } from "@/lib/components/ui";
import { type ArtifactWithSession, isProjectArtifact } from "@/lib/api/artifacts";
import { getArtifactContent } from "@/lib/utils";
import { cn } from "@/lib/utils";

import { AttachmentCardShell, AttachmentInlineText } from "./AttachmentCardShell";
import { DocumentThumbnail, supportsThumbnail } from "./DocumentThumbnail";
import { getFileTypeColor } from "./FileIcon";
import { MAX_THUMBNAIL_FILE_BYTES, getExtensionLabel, isImageType, supportsTextPreview } from "./attachmentUtils";

interface ArtifactAttachmentCardProps {
    artifact: ArtifactWithSession;
    onClick?: () => void;
    onRemove?: () => void;
}

function decodeBase64Snippet(base64: string): string {
    try {
        // base64 is ~4/3 the byte size — ~1.4 KB covers ~1 KB of text.
        // atob requires a full quartet, so trim any trailing partial group.
        const cleaned = base64.slice(0, 1400).replace(/\s/g, "");
        const len = cleaned.length - (cleaned.length % 4);
        if (len === 0) return "";
        const binary = atob(cleaned.slice(0, len));
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    } catch {
        return "";
    }
}

/**
 * Card-style chip for an attached existing artifact. Mirrors the form factor
 * of PendingPastedTextBadge: for text the content renders inline (card height
 * tracks content); for images / documents a compact preview box is used.
 */
export const ArtifactAttachmentCard: React.FC<ArtifactAttachmentCardProps> = ({ artifact, onClick, onRemove }) => {
    // Skip thumbnail fetches for oversized artifacts — same threshold as
    // FileUploadCard. Falls back to the extension pill instead.
    const tooLargeToThumb = typeof artifact.size === "number" && artifact.size > MAX_THUMBNAIL_FILE_BYTES;

    const isImage = !tooLargeToThumb && isImageType(artifact.mime_type, artifact.filename);
    const isDoc = !tooLargeToThumb && supportsThumbnail(artifact.filename, artifact.mime_type);
    // PPTX/DOCX mime types contain the substring "xml" (from "…presentationml…",
    // "…wordprocessingml…"), which would otherwise match supportsTextPreview
    // and render the binary zip as text. Documents take precedence.
    const isText = !tooLargeToThumb && !isDoc && !isImage && supportsTextPreview(artifact.mime_type, artifact.filename);
    const needsFetch = isImage || isDoc || isText;

    // Mirror the contract used by `getArtifactApiUrl`: only treat as project-scoped
    // when projectId is actually set. Project artifacts missing a projectId fall
    // back to session-scoped fetch so the request hits a real path.
    const projectId = isProjectArtifact(artifact) && artifact.projectId ? artifact.projectId : undefined;
    const sessionId = projectId ? undefined : artifact.sessionId;

    const { data, isLoading, isError } = useQuery({
        // Without a version, getArtifactUrl returns the list-versions endpoint
        // (responds with [0,1]). Pin to "latest" to always fetch the raw bytes.
        queryKey: ["artifact-attachment-preview", projectId ?? null, sessionId ?? null, artifact.filename, "latest"],
        queryFn: () => getArtifactContent({ filename: artifact.filename, sessionId, projectId, version: "latest" }),
        enabled: needsFetch,
        staleTime: 5 * 60 * 1000,
        retry: 1,
    });

    const textSnippet = useMemo(() => {
        if (!isText || !data?.content) return null;
        const decoded = decodeBase64Snippet(data.content);
        if (!decoded) return null;
        const lines = decoded.split("\n").map(line => line.trimEnd());
        return lines.join("\n");
    }, [isText, data?.content]);

    const imageDataUrl = useMemo(() => {
        if (!isImage || !data?.content) return null;
        return `data:${data.mimeType || artifact.mime_type};base64,${data.content}`;
    }, [isImage, data, artifact.mime_type]);

    // Track document-thumbnail render failure (e.g. 413 from the conversion
    // service for large Office files) so we can fall back to the extension pill.
    const [docFailed, setDocFailed] = useState(false);
    useEffect(() => {
        setDocFailed(false);
    }, [artifact.filename, artifact.sessionId, artifact.projectId]);

    // Text renders inline (no fixed preview box) so card height tracks the paste card.
    const inlineText = isText && !!textSnippet;
    const textLines = useMemo(() => (textSnippet ? textSnippet.split("\n") : []), [textSnippet]);

    const preview = (() => {
        if (needsFetch && isLoading) {
            return (
                <div className="flex h-full items-center justify-center">
                    <Spinner size="small" variant="muted" />
                </div>
            );
        }

        if (isImage && imageDataUrl && !isError) {
            return <img src={imageDataUrl} alt={artifact.filename} className="h-full w-full object-cover" />;
        }

        if (isDoc && data?.content && !isError && !docFailed) {
            return <DocumentThumbnail content={data.content} filename={artifact.filename} mimeType={artifact.mime_type} width={200} height={80} className="h-full w-full" onError={() => setDocFailed(true)} />;
        }

        return (
            <div className="flex h-full w-full items-center justify-center">
                <span className={cn("rounded px-2 py-0.5 text-[10px] font-bold text-(--darkSurface-text)", getFileTypeColor(artifact.mime_type, artifact.filename))}>{getExtensionLabel(artifact.filename)}</span>
            </div>
        );
    })();

    const scopeLabel = artifact.projectName || artifact.sessionName;
    const tooltipText = `Preview ${artifact.filename}${scopeLabel ? ` · ${scopeLabel}` : ""}`;

    return (
        <AttachmentCardShell
            filename={artifact.filename}
            preview={preview}
            inlineText={inlineText ? <AttachmentInlineText lines={textLines} /> : undefined}
            tooltipText={tooltipText}
            onClick={onClick}
            onRemove={onRemove}
            removeTooltip="Remove attached artifact"
        />
    );
};
