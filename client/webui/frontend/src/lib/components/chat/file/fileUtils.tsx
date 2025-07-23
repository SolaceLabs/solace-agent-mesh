import { File, FileAudio, FileCode, FileImage, FileJson, FileSpreadsheet, FileText } from "lucide-react";

import type { ArtifactInfo } from "@/lib/types";

import { getRenderType } from "../preview/previewUtils";

export const getFileIcon = (artifact: ArtifactInfo | undefined, className = "h-4 w-4") => {
    if (!artifact) {
        return <File className={className} />;
    }

    const type = getRenderType(artifact.filename, artifact.mime_type);

    switch (type) {
        case "image":
        case "mermaid":
            return <FileImage className={className} />;
        case "audio":
            return <FileAudio className={className} />;
        case "html":
            return <FileCode className={className} />;
        case "text":
            return <FileText className={className} />;
        case "csv":
            return <FileSpreadsheet className={className} />;
        case "json":
            return <FileJson className={className} />;
        default:
            return <File className={className} />;
    }
};
