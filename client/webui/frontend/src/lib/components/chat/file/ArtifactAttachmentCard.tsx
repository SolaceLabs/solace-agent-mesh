import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { XIcon } from "lucide-react";

import { Button, Spinner, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { ArtifactWithSession } from "@/lib/api/artifacts";
import { getArtifactContent } from "@/lib/utils";
import { cn } from "@/lib/utils";

import { DocumentThumbnail, supportsThumbnail } from "./DocumentThumbnail";
import { getFileTypeColor } from "./FileIcon";
import { isProjectArtifact } from "./StandaloneArtifactPreview";

interface ArtifactAttachmentCardProps {
    artifact: ArtifactWithSession;
    onClick?: () => void;
    onRemove?: () => void;
}

function isImageType(mimeType: string): boolean {
    return mimeType.startsWith("image/");
}

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

function getExtensionLabel(filename: string): string {
    const parts = filename.split(".");
    const ext = parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
    return ext.length > 4 ? ext.substring(0, 4) : ext;
}

function decodeBase64Snippet(base64: string): string {
    try {
        // base64 is ~4/3 the byte size — ~1.4 KB covers ~1 KB of text.
        const trimmed = base64.slice(0, 1400);
        const binary = atob(trimmed.replace(/\s/g, ""));
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
    const isImage = isImageType(artifact.mime_type);
    const isDoc = supportsThumbnail(artifact.filename, artifact.mime_type);
    // PPTX/DOCX mime types contain the substring "xml" (from "…presentationml…",
    // "…wordprocessingml…"), which would otherwise match supportsTextPreview
    // and render the binary zip as text. Documents take precedence.
    const isText = !isDoc && !isImage && supportsTextPreview(artifact.mime_type);
    const needsFetch = isImage || isDoc || isText;

    const sessionId = isProjectArtifact(artifact) ? undefined : artifact.sessionId;
    const projectId = isProjectArtifact(artifact) ? artifact.projectId : undefined;

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

    const clickable = Boolean(onClick);

    // Track document-thumbnail render failure (e.g. 413 from the conversion
    // service for large Office files) so we can fall back to the extension pill.
    const [docFailed, setDocFailed] = useState(false);
    useEffect(() => {
        setDocFailed(false);
    }, [artifact.filename, artifact.sessionId, artifact.projectId]);

    // Text renders inline (no fixed preview box) so card height tracks the paste card.
    const inlineText = isText && !!textSnippet;
    const textLines = useMemo(() => (textSnippet ? textSnippet.split("\n") : []), [textSnippet]);

    const fixedPreview = (() => {
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

    const CardBody = (
        <div
            className={cn("relative inline-flex w-[200px] flex-col rounded-lg border bg-(--background-w10) shadow-sm transition-colors", clickable && "cursor-pointer hover:border-(--primary-w20)")}
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
            onClick={clickable ? onClick : undefined}
            onKeyDown={
                clickable
                    ? event => {
                          if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onClick?.();
                          }
                      }
                    : undefined
            }
        >
            {onRemove && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={event => {
                        event.stopPropagation();
                        onRemove();
                    }}
                    className="absolute -top-2 -left-2 z-10 h-5 w-5 rounded-full border bg-(--background-w10) p-0 shadow-sm hover:bg-(--secondary-w10)"
                    tooltip="Remove attached artifact"
                    tooltipSide="left"
                >
                    <XIcon className="h-3 w-3" />
                </Button>
            )}

            {inlineText ? (
                <div className="overflow-hidden px-3 pt-3 pb-2 font-mono text-xs leading-relaxed text-(--secondary-text-wMain)">
                    {textLines.slice(0, 2).map((line, index) => {
                        const trimmed = line.trim();
                        const display = trimmed.length > 40 ? trimmed.substring(0, 37) + "..." : trimmed;
                        return (
                            <div key={`${index}-${line}`} className="truncate">
                                {display || " "}
                            </div>
                        );
                    })}
                    {textLines.length > 2 && <div className="text-(--secondary-text-w50)">...</div>}
                </div>
            ) : (
                <div className="relative h-20 w-full overflow-hidden rounded-t-lg bg-(--secondary-w10)">{fixedPreview}</div>
            )}

            <div className="flex items-center gap-1 px-2 pb-2">
                <span className="inline-block max-w-[170px] truncate rounded bg-(--secondary-w10) px-2 py-0.5 text-[10px] font-semibold tracking-wider text-(--secondary-text-wMain)" title={artifact.filename}>
                    {artifact.filename}
                </span>
            </div>
        </div>
    );

    if (!clickable) return CardBody;

    return (
        <Tooltip>
            <TooltipTrigger asChild>{CardBody}</TooltipTrigger>
            <TooltipContent side="top">
                <p>{tooltipText}</p>
            </TooltipContent>
        </Tooltip>
    );
};
