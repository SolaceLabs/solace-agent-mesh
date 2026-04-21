import React, { useEffect, useMemo, useState } from "react";
import { XIcon } from "lucide-react";

import { Button, Spinner, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

import { DocumentThumbnail, supportsThumbnail } from "./DocumentThumbnail";
import { getFileTypeColor } from "./FileIcon";

interface FileUploadCardProps {
    file: File;
    onRemove?: () => void;
    /**
     * Override the default click behavior. When omitted, clicking opens the
     * file in a new tab via a blob URL — PDFs and images render natively in
     * the browser; other types trigger the browser's default handler.
     */
    onClick?: () => void;
}

// Don't base64-encode huge binaries just to render a thumbnail.
const MAX_THUMBNAIL_FILE_BYTES = 20 * 1024 * 1024; // 20 MB

function isImageType(mimeType: string, filename: string): boolean {
    if (mimeType.startsWith("image/")) return true;
    const ext = filename.toLowerCase().split(".").pop();
    return !!ext && ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "ico"].includes(ext);
}

function supportsTextPreview(mimeType: string, filename: string): boolean {
    if (mimeType.startsWith("text/")) return true;
    if (["json", "xml", "javascript", "typescript", "markdown", "yaml", "yml"].some(k => mimeType.includes(k))) return true;
    const ext = filename.toLowerCase().split(".").pop();
    return !!ext && ["txt", "md", "markdown", "json", "yaml", "yml", "xml", "html", "htm", "css", "scss", "js", "jsx", "ts", "tsx", "py", "java", "c", "cpp", "h", "sh", "log", "csv", "tsv", "ini", "toml"].includes(ext);
}

function getExtensionLabel(filename: string): string {
    const parts = filename.split(".");
    const ext = parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
    return ext.length > 4 ? ext.substring(0, 4) : ext;
}

/**
 * Thumbnail card for a user-selected local file that hasn't been uploaded yet.
 * Mirrors the form factor of ArtifactAttachmentCard and PendingPastedTextBadge.
 * Thumbnails are generated from the File object in-browser — no network calls.
 */
export const FileUploadCard: React.FC<FileUploadCardProps> = ({ file, onRemove, onClick }) => {
    const tooSmallToThumb = file.size === 0;
    const tooLargeToThumb = file.size > MAX_THUMBNAIL_FILE_BYTES;

    const isImage = !tooLargeToThumb && isImageType(file.type, file.name);
    const isDoc = !tooLargeToThumb && supportsThumbnail(file.name, file.type);
    // PPTX/DOCX mime types contain the substring "xml", which would otherwise
    // match supportsTextPreview and cause the binary zip to render as text.
    // Treat document-thumbnail types as docs exclusively.
    const isText = !tooLargeToThumb && !tooSmallToThumb && !isDoc && !isImage && supportsTextPreview(file.type, file.name);

    // Images: use object URLs (cheap, revoked on unmount).
    const imageObjectUrl = useMemo(() => (isImage ? URL.createObjectURL(file) : null), [isImage, file]);
    useEffect(() => {
        return () => {
            if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
        };
    }, [imageObjectUrl]);

    // Documents: read as base64 for DocumentThumbnail. Track render failure
    // (e.g. backend conversion returns 413 for large pptx) to fall back to the
    // extension pill instead of leaving the preview area empty.
    const [docBase64, setDocBase64] = useState<string | null>(null);
    const [docLoading, setDocLoading] = useState(false);
    const [docFailed, setDocFailed] = useState(false);
    useEffect(() => {
        if (!isDoc) return;
        let cancelled = false;
        setDocLoading(true);
        setDocFailed(false);
        const reader = new FileReader();
        reader.onload = () => {
            if (cancelled) return;
            const result = reader.result as string;
            // strip "data:...;base64," prefix
            const commaIdx = result.indexOf(",");
            setDocBase64(commaIdx >= 0 ? result.substring(commaIdx + 1) : result);
            setDocLoading(false);
        };
        reader.onerror = () => {
            if (!cancelled) setDocLoading(false);
        };
        reader.readAsDataURL(file);
        return () => {
            cancelled = true;
            reader.abort();
        };
    }, [isDoc, file]);

    // Text: read first 2 KB, decode as utf-8, show first few lines.
    const [textSnippet, setTextSnippet] = useState<string | null>(null);
    const [textLoading, setTextLoading] = useState(false);
    useEffect(() => {
        if (!isText) return;
        let cancelled = false;
        setTextLoading(true);
        file.slice(0, 2048)
            .text()
            .then(text => {
                if (!cancelled) {
                    setTextSnippet(text);
                    setTextLoading(false);
                }
            })
            .catch(() => {
                if (!cancelled) setTextLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [isText, file]);

    const textLines = useMemo(() => (textSnippet ? textSnippet.split("\n").map(l => l.trimEnd()) : []), [textSnippet]);
    const inlineText = isText && textLines.length > 0;

    const openBlobInNewTab = () => {
        const url = URL.createObjectURL(file);
        const tab = window.open(url, "_blank", "noopener,noreferrer");
        // Revoke after a delay so the tab has time to load the blob.
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        if (!tab) URL.revokeObjectURL(url);
    };
    const handleClick = onClick ?? openBlobInNewTab;
    const clickable = true;

    const fixedPreview = (() => {
        if (isImage && imageObjectUrl) {
            return <img src={imageObjectUrl} alt={file.name} className="h-full w-full object-cover" />;
        }

        if (isDoc && !docFailed) {
            if (docLoading || !docBase64) {
                return (
                    <div className="flex h-full items-center justify-center">
                        <Spinner size="small" variant="muted" />
                    </div>
                );
            }
            return <DocumentThumbnail content={docBase64} filename={file.name} mimeType={file.type} width={200} height={80} className="h-full w-full" onError={() => setDocFailed(true)} />;
        }

        if (isText && textLoading) {
            return (
                <div className="flex h-full items-center justify-center">
                    <Spinner size="small" variant="muted" />
                </div>
            );
        }

        return (
            <div className="flex h-full w-full items-center justify-center">
                <span className={cn("rounded px-2 py-0.5 text-[10px] font-bold text-(--darkSurface-text)", getFileTypeColor(file.type, file.name))}>{getExtensionLabel(file.name)}</span>
            </div>
        );
    })();

    const CardBody = (
        <div
            className={cn("relative inline-flex w-[200px] flex-col rounded-lg border bg-(--background-w10) shadow-sm transition-colors", clickable && "cursor-pointer hover:border-(--primary-w20)")}
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
            onClick={handleClick}
            onKeyDown={
                clickable
                    ? event => {
                          if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleClick();
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
                    tooltip="Remove file"
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
                                {display || " "}
                            </div>
                        );
                    })}
                    {textLines.length > 2 && <div className="text-(--secondary-text-w50)">...</div>}
                </div>
            ) : (
                <div className="relative h-20 w-full overflow-hidden rounded-t-lg bg-(--secondary-w10)">{fixedPreview}</div>
            )}

            <div className="flex items-center gap-1 px-2 pb-2">
                <span className="inline-block max-w-[170px] truncate rounded bg-(--secondary-w10) px-2 py-0.5 text-[10px] font-semibold tracking-wider text-(--secondary-text-wMain)" title={file.name}>
                    {file.name}
                </span>
            </div>
        </div>
    );

    if (!clickable) return CardBody;

    return (
        <Tooltip>
            <TooltipTrigger asChild>{CardBody}</TooltipTrigger>
            <TooltipContent side="top">
                <p>{file.name}</p>
            </TooltipContent>
        </Tooltip>
    );
};
