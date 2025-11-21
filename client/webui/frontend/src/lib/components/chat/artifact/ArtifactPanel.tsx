import React, { useMemo, useState } from "react";

import { ArrowDown, ArrowLeft, Ellipsis, FileText, Loader2 } from "lucide-react";

import { Button } from "@/lib/components";
import { useChatContext, useDownload } from "@/lib/hooks";
import type { ArtifactInfo } from "@/lib/types";
import { formatBytes } from "@/lib/utils/format";

import { ArtifactCard } from "./ArtifactCard";
import { ArtifactDeleteDialog } from "./ArtifactDeleteDialog";
import { ArtifactPreviewContent } from "./ArtifactPreviewContent";
import { SortOption, SortPopover, type SortOptionType } from "./ArtifactSortPopover";
import { ArtifactMorePopover } from "./ArtifactMorePopover";
import { ArtifactDeleteAllDialog } from "./ArtifactDeleteAllDialog";
import { ArtifactDetails } from "./ArtifactDetails";

const sortFunctions: Record<SortOptionType, (a1: ArtifactInfo, a2: ArtifactInfo) => number> = {
    [SortOption.NameAsc]: (a1, a2) => a1.filename.localeCompare(a2.filename),
    [SortOption.NameDesc]: (a1, a2) => a2.filename.localeCompare(a1.filename),
    [SortOption.DateAsc]: (a1, a2) => (a1.last_modified > a2.last_modified ? 1 : -1),
    [SortOption.DateDesc]: (a1, a2) => (a1.last_modified < a2.last_modified ? 1 : -1),
};

export const ArtifactPanel: React.FC = () => {
    const { artifacts, artifactsLoading, previewArtifact, setPreviewArtifact, artifactsRefetch, openDeleteModal } = useChatContext();
    const { onDownload } = useDownload();

    const [sortOption, setSortOption] = useState<SortOptionType>(SortOption.DateDesc);
    const [isPreviewInfoExpanded, setIsPreviewInfoExpanded] = useState(false);
    const sortedArtifacts = useMemo(() => {
        if (artifactsLoading) return [];

        return artifacts ? [...artifacts].sort(sortFunctions[sortOption]) : [];
    }, [artifacts, artifactsLoading, sortOption]);

    // Check if there are any deletable artifacts (not from projects)
    const hasDeletableArtifacts = useMemo(() => {
        return sortedArtifacts.some(artifact => artifact.source !== "project");
    }, [sortedArtifacts]);

    const header = useMemo(() => {
        if (previewArtifact) {
            return (
                <div className="flex items-center gap-2 border-b p-2">
                    <Button variant="ghost" onClick={() => setPreviewArtifact(null)}>
                        <ArrowLeft />
                    </Button>
                    <div className="text-md font-semibold">Preview</div>
                </div>
            );
        }

        return (
            sortedArtifacts.length > 0 && (
                <div className="flex items-center justify-end border-b p-2">
                    <SortPopover key="sort-popover" currentSortOption={sortOption} onSortChange={setSortOption}>
                        <Button variant="ghost" title="Sort By">
                            <ArrowDown className="h-5 w-5" />
                            <div>Sort By</div>
                        </Button>
                    </SortPopover>
                    <ArtifactMorePopover key="more-popover" hideDeleteAll={!hasDeletableArtifacts}>
                        <Button variant="ghost" tooltip="More">
                            <Ellipsis className="h-5 w-5" />
                        </Button>
                    </ArtifactMorePopover>
                </div>
            )
        );
    }, [previewArtifact, sortedArtifacts.length, sortOption, setPreviewArtifact, hasDeletableArtifacts]);

    return (
        <div className="flex h-full flex-col">
            {header}
            <div className="flex min-h-0 flex-1">
                {!previewArtifact && (
                    <div className="flex-1 overflow-y-auto">
                        {sortedArtifacts.map(artifact => (
                            <ArtifactCard key={artifact.filename} artifact={artifact} />
                        ))}
                        {sortedArtifacts.length === 0 && (
                            <div className="flex h-full items-center justify-center p-4">
                                <div className="text-muted-foreground text-center">
                                    {artifactsLoading && <Loader2 className="size-6 animate-spin" />}
                                    {!artifactsLoading && (
                                        <>
                                            <FileText className="mx-auto mb-4 h-12 w-12" />
                                            <div className="text-lg font-medium">Files</div>
                                            <div className="mt-2 text-sm">No files available</div>
                                            <Button className="mt-4" variant="default" onClick={artifactsRefetch} data-testid="refreshFiles" title="Refresh Files">
                                                Refresh
                                            </Button>
                                        </>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}
                {previewArtifact && (
                    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
                        <div className="border-b px-4 py-3">
                            <ArtifactDetails
                                artifactInfo={previewArtifact}
                                isPreview={true}
                                isExpanded={isPreviewInfoExpanded}
                                setIsExpanded={setIsPreviewInfoExpanded}
                                onDelete={previewArtifact.source === "project" ? undefined : () => openDeleteModal(previewArtifact)}
                                onDownload={() => onDownload(previewArtifact)}
                            />
                        </div>
                        {isPreviewInfoExpanded && (
                            <div className="border-b px-4 py-3">
                                <div className="space-y-2 text-sm">
                                    {previewArtifact.description && (
                                        <div>
                                            <span className="text-secondary-foreground">Description:</span>
                                            <div className="mt-1">{previewArtifact.description}</div>
                                        </div>
                                    )}
                                    <div className="grid grid-cols-2 gap-2">
                                        <div>
                                            <span className="text-secondary-foreground">Size:</span>
                                            <div>{formatBytes(previewArtifact.size)}</div>
                                        </div>
                                        <div>
                                            <span className="text-secondary-foreground">Type:</span>
                                            <div>{previewArtifact.mime_type || 'Unknown'}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
                            <ArtifactPreviewContent artifact={previewArtifact} />
                        </div>
                    </div>
                )}
            </div>
            <ArtifactDeleteDialog />
            <ArtifactDeleteAllDialog />
        </div>
    );
};
