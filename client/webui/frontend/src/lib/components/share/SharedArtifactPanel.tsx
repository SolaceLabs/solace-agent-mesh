/**
 * SharedArtifactPanel - Read-only artifact list for shared sessions
 *
 * This is a simplified version of ArtifactPanel that displays artifacts
 * without the full preview/download functionality since shared sessions
 * may not have access to the artifact content.
 */

import React, { useMemo, useState } from "react";
import { ArrowDown, FileText, File, Image, Music, Video, FileCode, FileSpreadsheet, FileArchive } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { formatBytes } from "@/lib/utils/format";
import type { SharedArtifact } from "@/lib/types/share";

interface SharedArtifactPanelProps {
    artifacts: SharedArtifact[];
}

type SortOption = "name-asc" | "name-desc" | "date-asc" | "date-desc";

const sortFunctions: Record<SortOption, (a1: SharedArtifact, a2: SharedArtifact) => number> = {
    "name-asc": (a1, a2) => a1.filename.localeCompare(a2.filename),
    "name-desc": (a1, a2) => a2.filename.localeCompare(a1.filename),
    "date-asc": (a1, a2) => {
        const d1 = a1.last_modified || "";
        const d2 = a2.last_modified || "";
        return d1.localeCompare(d2);
    },
    "date-desc": (a1, a2) => {
        const d1 = a1.last_modified || "";
        const d2 = a2.last_modified || "";
        return d2.localeCompare(d1);
    },
};

/**
 * Get an appropriate icon for a file based on its mime type
 */
function getFileIcon(mimeType: string): React.ReactNode {
    if (mimeType.startsWith("image/")) {
        return <Image className="h-5 w-5 text-blue-500" />;
    }
    if (mimeType.startsWith("audio/")) {
        return <Music className="h-5 w-5 text-purple-500" />;
    }
    if (mimeType.startsWith("video/")) {
        return <Video className="h-5 w-5 text-pink-500" />;
    }
    if (mimeType.includes("spreadsheet") || mimeType === "text/csv") {
        return <FileSpreadsheet className="h-5 w-5 text-green-500" />;
    }
    if (mimeType.includes("zip") || mimeType.includes("archive") || mimeType.includes("compressed")) {
        return <FileArchive className="h-5 w-5 text-yellow-500" />;
    }
    if (
        mimeType.includes("javascript") ||
        mimeType.includes("typescript") ||
        mimeType.includes("json") ||
        mimeType.includes("xml") ||
        mimeType.includes("html") ||
        mimeType.includes("css") ||
        mimeType.includes("python") ||
        mimeType.includes("java") ||
        mimeType.includes("code")
    ) {
        return <FileCode className="h-5 w-5 text-orange-500" />;
    }
    if (mimeType.startsWith("text/") || mimeType === "application/pdf") {
        return <FileText className="h-5 w-5 text-gray-500" />;
    }
    return <File className="h-5 w-5 text-gray-400" />;
}

export const SharedArtifactPanel: React.FC<SharedArtifactPanelProps> = ({ artifacts }) => {
    const [sortOption, setSortOption] = useState<SortOption>("date-desc");
    const [showSortMenu, setShowSortMenu] = useState(false);

    const sortedArtifacts = useMemo(() => {
        return [...artifacts].sort(sortFunctions[sortOption]);
    }, [artifacts, sortOption]);

    const handleSortChange = (option: SortOption) => {
        setSortOption(option);
        setShowSortMenu(false);
    };

    if (artifacts.length === 0) {
        return (
            <div className="flex h-full items-center justify-center p-4">
                <div className="text-muted-foreground text-center">
                    <FileText className="mx-auto mb-4 h-12 w-12" />
                    <div className="text-lg font-medium">Files</div>
                    <div className="mt-2 text-sm">No files in this session</div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col">
            {/* Header with sort */}
            <div className="relative flex items-center justify-end border-b p-2">
                <Button variant="ghost" size="sm" onClick={() => setShowSortMenu(!showSortMenu)} className="flex items-center gap-1">
                    <ArrowDown className="h-4 w-4" />
                    <span>Sort</span>
                </Button>

                {showSortMenu && (
                    <div className="bg-popover absolute top-full right-2 z-10 mt-1 rounded-md border shadow-md">
                        <div className="p-1">
                            <button className={`hover:bg-accent w-full rounded px-3 py-1.5 text-left text-sm ${sortOption === "name-asc" ? "bg-accent" : ""}`} onClick={() => handleSortChange("name-asc")}>
                                Name (A-Z)
                            </button>
                            <button className={`hover:bg-accent w-full rounded px-3 py-1.5 text-left text-sm ${sortOption === "name-desc" ? "bg-accent" : ""}`} onClick={() => handleSortChange("name-desc")}>
                                Name (Z-A)
                            </button>
                            <button className={`hover:bg-accent w-full rounded px-3 py-1.5 text-left text-sm ${sortOption === "date-desc" ? "bg-accent" : ""}`} onClick={() => handleSortChange("date-desc")}>
                                Newest First
                            </button>
                            <button className={`hover:bg-accent w-full rounded px-3 py-1.5 text-left text-sm ${sortOption === "date-asc" ? "bg-accent" : ""}`} onClick={() => handleSortChange("date-asc")}>
                                Oldest First
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Artifact list */}
            <div className="flex-1 overflow-y-auto">
                {sortedArtifacts.map((artifact, index) => (
                    <div key={`${artifact.filename}-${index}`} className="border-b p-3 last:border-b-0">
                        <div className="flex items-start gap-3">
                            <div className="mt-0.5 flex-shrink-0">{getFileIcon(artifact.mime_type)}</div>
                            <div className="min-w-0 flex-1">
                                <div className="truncate font-medium" title={artifact.filename}>
                                    {artifact.filename}
                                </div>
                                <div className="text-muted-foreground mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                    <span>{formatBytes(artifact.size)}</span>
                                    <span className="truncate">{artifact.mime_type}</span>
                                    {artifact.version && <span>v{artifact.version}</span>}
                                </div>
                                {artifact.description && <div className="text-muted-foreground mt-1 line-clamp-2 text-xs">{artifact.description}</div>}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
