import { File } from "lucide-react";

export const FileLabel = ({ fileName, fileSize }: { fileName: string; fileSize: number }) => {
    return (
        <div className="flex items-center gap-3">
            <File className="text-muted-foreground size-5" />
            <div className="overflow-hidden">
                <div className="line-clamp-2 break-all" title={fileName}>
                    {fileName}
                </div>
                <div className="text-muted-foreground text-xs">{(fileSize / 1024).toFixed(1)} KB</div>
            </div>
        </div>
    );
};
