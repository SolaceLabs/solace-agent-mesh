import React, { useState, useCallback, useEffect } from "react";

import { Textarea } from "@/lib/components/ui";
import { MessageBanner, ConfirmationDialog } from "@/lib/components/common";
import { FileLabel } from "../chat/file/FileLabel";

interface AddProjectFilesDialogProps {
    isOpen: boolean;
    files: FileList | null;
    onClose: () => void;
    onConfirm: (formData: FormData) => void;
    isSubmitting?: boolean;
    error?: string | null;
    onClearError?: () => void;
}

export const AddProjectFilesDialog: React.FC<AddProjectFilesDialogProps> = ({ isOpen, files, onClose, onConfirm, isSubmitting = false, error = null, onClearError }) => {
    const [fileDescriptions, setFileDescriptions] = useState<Record<string, string>>({});

    useEffect(() => {
        // Reset descriptions when the dialog is opened with new files
        if (isOpen) {
            setFileDescriptions({});
        }
    }, [isOpen]);

    const handleClose = useCallback(() => {
        onClearError?.();
        onClose();
    }, [onClose, onClearError]);

    const handleFileDescriptionChange = useCallback((fileName: string, description: string) => {
        setFileDescriptions(prev => ({
            ...prev,
            [fileName]: description,
        }));
    }, []);

    const handleConfirmClick = useCallback(async () => {
        if (!files) return;

        const formData = new FormData();
        const metadataPayload: Record<string, string> = {};

        for (const file of Array.from(files)) {
            formData.append("files", file);
            if (fileDescriptions[file.name]) {
                metadataPayload[file.name] = fileDescriptions[file.name];
            }
        }

        if (Object.keys(metadataPayload).length > 0) {
            formData.append("fileMetadata", JSON.stringify(metadataPayload));
        }

        await onConfirm(formData);
    }, [files, fileDescriptions, onConfirm]);

    const fileList = files ? Array.from(files) : [];

    const dialogContent = (
        <>
            {error && <MessageBanner variant="error" message={error} dismissible onDismiss={onClearError} />}
            {fileList.length > 0 ? (
                <div className="mt-4 flex max-h-[50vh] flex-col gap-4 overflow-y-auto p-1">
                    {fileList.map((file, index) => (
                        <div key={file.name + index}>
                            <FileLabel fileName={file.name} fileSize={file.size} />
                            <Textarea className="mt-2" rows={2} disabled={isSubmitting} value={fileDescriptions[file.name] || ""} onChange={e => handleFileDescriptionChange(file.name, e.target.value)} />
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-muted-foreground">No files selected.</p>
            )}
        </>
    );

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={open => !open && handleClose()}
            title="Upload Project Files"
            description="Add descriptions to help Solace Agent Mesh understand each file's purpose."
            content={dialogContent}
            actionLabels={{
                cancel: "Cancel",
                confirm: `Upload ${fileList.length} File(s)`,
            }}
            isLoading={isSubmitting}
            onConfirm={handleConfirmClick}
            onCancel={handleClose}
        />
    );
};
