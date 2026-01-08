import React from "react";

import { Download } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { useDownload } from "@/lib/hooks/useDownload";
import type { ArtifactInfo } from "@/lib/types";

interface ArtifactPreviewDownloadProps {
    artifact: ArtifactInfo;
    message: string;
}

export const ArtifactPreviewDownload: React.FC<ArtifactPreviewDownloadProps> = ({ artifact, message }) => {
    const { onDownload } = useDownload();

    return (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 p-4">
            <div className="mb-1 font-semibold">Preview Unavailable</div>
            <div>{message}</div>
            <Button onClick={() => onDownload(artifact)}>
                <Download className="h-4 w-4" />
                Download
            </Button>
        </div>
    );
};
