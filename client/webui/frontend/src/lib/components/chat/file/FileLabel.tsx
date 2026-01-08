import { formatBytes } from "@/lib/utils";
import { File } from "lucide-react";

export const FileLabel = ({ fileName, fileSize }: { fileName: string; fileSize: number }) => {
    return (
        <div className="flex items-center gap-3">
            <File className="text-muted-foreground size-5 shrink-0" />
            <div className="overflow-hidden">
                <div className="truncate" title={fileName}>
                    {fileName}
                </div>
                <div className="text-muted-foreground text-xs">{formatBytes(fileSize)}</div>
            </div>
        </div>
    );
};
