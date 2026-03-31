import React from "react";
import { Download, FileType } from "lucide-react";

interface NoPreviewStateProps {
    documentType?: string;
    error?: string;
}

export const NoPreviewState: React.FC<NoPreviewStateProps> = ({ documentType, error }) => (
    <div className="flex h-64 flex-col items-center justify-center space-y-4 p-6 text-center">
        <FileType className="h-16 w-16 text-(--secondary-text-wMain)" />
        <div>
            <h3 className="text-lg font-semibold">Preview Unavailable</h3>
            {documentType && <p className="mt-2 text-(--secondary-text-wMain)">Unable to preview this {documentType.toUpperCase()} file.</p>}
            {error && <p className="mt-1 text-sm text-(--secondary-text-wMain)">{error}</p>}
            <p className="mt-4 flex items-center justify-center gap-2 text-sm text-(--secondary-text-wMain)">
                <Download className="h-4 w-4" />
                Download the file to open it in the appropriate application.
            </p>
        </div>
    </div>
);
