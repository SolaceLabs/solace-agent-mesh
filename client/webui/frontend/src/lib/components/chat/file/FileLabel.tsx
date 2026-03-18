import { formatBytes } from "@/lib/utils";
import { File } from "lucide-react";

export const FileLabel = ({ fileName, fileSize }: { fileName: string; fileSize: number }) => {
    return (
        <div className="flex items-center gap-3">
            <File className="size-5 shrink-0 text-(--secondary-text-wMain)" />
            <div className="overflow-hidden">
                <div className="truncate" title={fileName}>
                    {fileName}
                </div>
                <div className="text-xs text-(--secondary-text-wMain)">{formatBytes(fileSize)}</div>
            </div>
        </div>
    );
};
