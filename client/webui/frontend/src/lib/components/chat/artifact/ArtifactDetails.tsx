import React, { useMemo } from "react";

import { Download, Info, Trash } from "lucide-react";

import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import { formatRelativeTime } from "@/lib/utils/format";
import type { ArtifactInfo } from "@/lib/types";

interface ArtifactDetailsProps {
    artifactInfo: ArtifactInfo;
    isPreview?: boolean;
    isExpanded?: boolean;
    onDelete?: () => void;
    onDownload?: (artifact: ArtifactInfo) => void;
    setIsExpanded?: (expanded: boolean) => void;
    badge?: {
        label: string;
        icon: React.ReactNode;
        badgeComponent: React.ReactNode;
        readonly?: boolean;
    } | null;
}

export const ArtifactDetails: React.FC<ArtifactDetailsProps> = ({ artifactInfo, isPreview = false, isExpanded = false, onDelete, onDownload, setIsExpanded, badge }) => {
    const { previewedArtifactAvailableVersions, currentPreviewedVersionNumber, navigateArtifactVersion } = useChatContext();
    const versions = useMemo(() => previewedArtifactAvailableVersions ?? [], [previewedArtifactAvailableVersions]);

    return (
        <div className="flex flex-row justify-between gap-1">
            <div className="flex min-w-0 items-center gap-4">
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <div className="truncate text-sm" title={artifactInfo.filename}>
                            {artifactInfo.filename}
                        </div>
                        {badge && badge.badgeComponent}
                    </div>
                    <div className="truncate text-xs" title={formatRelativeTime(artifactInfo.last_modified)}>
                        {formatRelativeTime(artifactInfo.last_modified)}
                    </div>
                </div>

                {isPreview && versions.length > 1 && (
                    <div className="align-right">
                        <Select
                            value={currentPreviewedVersionNumber?.toString()}
                            onValueChange={value => {
                                navigateArtifactVersion(artifactInfo.filename, parseInt(value));
                            }}
                        >
                            <SelectTrigger className="h-[16px] py-0 text-xs shadow-none">
                                <SelectValue placeholder="Version" />
                            </SelectTrigger>
                            <SelectContent>
                                {versions.map(version => (
                                    <SelectItem key={version} value={version.toString()}>
                                        Version {version}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                )}
            </div>
            <div className={`whitespace-nowrap ${isPreview ? "opacity-100" : "opacity-0 transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100"}`}>
                {setIsExpanded && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={e => {
                            e.stopPropagation();
                            e.preventDefault();
                            setIsExpanded(!isExpanded);
                        }}
                        tooltip={isExpanded ? "Collapse Details" : "Expand Details"}
                    >
                        <Info />
                    </Button>
                )}
                {onDownload && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={async e => {
                            e.stopPropagation();
                            e.preventDefault();
                            await onDownload(artifactInfo);
                        }}
                        tooltip="Download"
                    >
                        <Download />
                    </Button>
                )}
                {onDelete && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={e => {
                            e.preventDefault();
                            e.stopPropagation();
                            onDelete();
                        }}
                        tooltip="Delete"
                    >
                        <Trash />
                    </Button>
                )}
            </div>
        </div>
    );
};
