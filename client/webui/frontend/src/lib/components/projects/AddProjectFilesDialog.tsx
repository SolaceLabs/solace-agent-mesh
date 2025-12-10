import React, { useState, useCallback, useEffect } from "react";
import { FileText } from "lucide-react";

import { Button, Card, Textarea } from "@/lib/components/ui";
import { CardContent } from "@/lib/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { MessageBanner } from "@/lib/components/common";

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

    const handleConfirmClick = useCallback(() => {
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

        onConfirm(formData);
    }, [files, fileDescriptions, onConfirm]);

    const fileList = files ? Array.from(files) : [];

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleClose()}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle>Upload Files to Project</DialogTitle>
                    <DialogDescription>Add descriptions for each file. This helps Solace Agent Mesh understand the file's purpose.</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    {error && <MessageBanner variant="error" message={error} dismissible onDismiss={onClearError} />}
                    {fileList.length > 0 ? (
                        <div className="max-h-[50vh] space-y-2 overflow-y-auto pr-2">
                            {fileList.map((file, index) => (
                                <Card key={index} noPadding className="bg-muted/50 overflow-hidden py-3 shadow-none">
                                    <CardContent noPadding className="overflow-hidden px-3">
                                        <div className="flex min-w-0 items-center gap-3">
                                            <FileText className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                                            <div className="min-w-0 flex-1 overflow-hidden">
                                                <p className="text-foreground line-clamp-2 text-sm font-medium break-all" title={file.name}>
                                                    {file.name}
                                                </p>
                                                <p className="text-muted-foreground text-xs">{(file.size / 1024).toFixed(1)} KB</p>
                                            </div>
                                        </div>
                                        <Textarea className="bg-background text-foreground mt-2" rows={2} disabled={isSubmitting} value={fileDescriptions[file.name] || ""} onChange={e => handleFileDescriptionChange(file.name, e.target.value)} />
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <p className="text-muted-foreground">No files selected.</p>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={handleClose} disabled={isSubmitting}>
                        Cancel
                    </Button>
                    <Button onClick={handleConfirmClick} disabled={isSubmitting || fileList.length === 0}>
                        {isSubmitting ? "Uploading..." : `Upload ${fileList.length} File(s)`}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
