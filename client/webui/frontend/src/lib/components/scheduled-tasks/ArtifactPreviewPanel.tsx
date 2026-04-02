import React from "react";
import { ArrowLeft, Download } from "lucide-react";
import type { ArtifactInfo } from "@/lib/types/scheduled-tasks";
import { Button } from "@/lib/components/ui";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { getRenderType } from "@/lib/components/chat/preview/previewUtils";

interface ArtifactPreviewPanelProps {
    artifact: ArtifactInfo;
    content: string | null;
    mimeType: string;
    isLoading: boolean;
    onClose: () => void;
    resolveArtifactUri: (uri: string) => string;
}

export const ArtifactPreviewPanel: React.FC<ArtifactPreviewPanelProps> = ({ artifact, content, mimeType, isLoading, onClose, resolveArtifactUri }) => {
    return (
        <div className="bg-background flex w-[450px] flex-shrink-0 flex-col">
            {/* Header with back button */}
            <div className="flex items-center gap-2 border-b p-2">
                <Button variant="ghost" onClick={onClose}>
                    <ArrowLeft />
                </Button>
                <div className="text-md font-semibold">Preview</div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-2">
                {/* Artifact Details */}
                <div className="border-b px-4 py-3">
                    <div className="flex flex-row justify-between gap-1">
                        <div className="flex min-w-0 items-center gap-4">
                            <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                    <div className="truncate text-sm" title={artifact.name}>
                                        {artifact.name}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div className="whitespace-nowrap">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    try {
                                        const resolved = resolveArtifactUri(artifact.uri);
                                        const url = new URL(resolved, window.location.origin);
                                        if (url.origin !== window.location.origin) {
                                            return;
                                        }
                                        window.open(`${url.href}?download=true`, "_blank");
                                    } catch {
                                        // Malformed URI — silently ignore
                                    }
                                }}
                                tooltip="Download"
                            >
                                <Download />
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Preview Content */}
                <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
                    {isLoading ? (
                        <div className="flex h-full items-center justify-center">
                            <div className="border-primary size-8 animate-spin rounded-full border-2 border-t-transparent" />
                        </div>
                    ) : content ? (
                        <div className="relative h-full w-full">
                            {(() => {
                                const rendererType = getRenderType(artifact.name, mimeType);
                                return rendererType ? <ContentRenderer content={content} rendererType={rendererType} mime_type={mimeType} setRenderError={() => {}} /> : <pre className="p-4 text-sm break-words whitespace-pre-wrap">{content}</pre>;
                            })()}
                        </div>
                    ) : (
                        <div className="flex h-full items-center justify-center">
                            <p className="text-sm text-(--secondary-text-wMain)">No content available</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
