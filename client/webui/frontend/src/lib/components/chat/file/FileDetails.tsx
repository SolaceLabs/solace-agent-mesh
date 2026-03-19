import React from "react";

import { formatBytes, formatRelativeTime } from "@/lib/utils/format";

interface FileDetailsProps {
    description?: string;
    size: number;
    lastModified: string;
    mimeType?: string;
}

export const FileDetails: React.FC<FileDetailsProps> = ({ description, size, lastModified, mimeType }) => {
    return (
        <div className="space-y-2 text-sm">
            {description && (
                <div>
                    <span className="text-(--secondary-text-wMain)">Description:</span>
                    <div className="mt-1">{description}</div>
                </div>
            )}
            <div className="grid grid-cols-2 gap-2">
                <div>
                    <span className="text-(--secondary-text-wMain)">Size:</span>
                    <div>{formatBytes(size)}</div>
                </div>
                <div>
                    <span className="text-(--secondary-text-wMain)">Modified:</span>
                    <div>{formatRelativeTime(lastModified)}</div>
                </div>
            </div>
            {mimeType && (
                <div>
                    <span className="text-(--secondary-text-wMain)">Type:</span>
                    <div>{mimeType}</div>
                </div>
            )}
        </div>
    );
};
