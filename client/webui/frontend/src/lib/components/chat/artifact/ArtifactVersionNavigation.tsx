import React, { useMemo } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo } from "@/lib/types";

interface ArtifactVersionNavigationProps {
    artifactInfo: ArtifactInfo;
}

export const ArtifactVersionNavigation: React.FC<ArtifactVersionNavigationProps> = ({ artifactInfo }) => {
    const { previewedArtifactAvailableVersions, currentPreviewedVersionNumber, navigateArtifactVersion } = useChatContext();
    const versions = useMemo(() => previewedArtifactAvailableVersions ?? [], [previewedArtifactAvailableVersions]);

    return (
        <>
            {versions.length > 1 ? (
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
            ) : null}
        </>
    );
};
