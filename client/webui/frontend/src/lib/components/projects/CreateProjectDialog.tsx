import React, { useState, useCallback, useEffect } from "react";
import { FileText } from "lucide-react";

import { Button, Card, CardContent, Textarea } from "@/lib/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";

interface AddProjectFilesDialogProps {
    isOpen: boolean;
    files: FileList | null;
    onClose: () => void;
    onConfirm: (formData: FormData) => void;
    isSubmitting?: boolean;
}

export const AddProjectFilesDialog: React.FC<AddProjectFilesDialogProps> = ({
    isOpen,
    files,
    onClose,
    onConfirm,
    isSubmitting = false,
}) => {
    const [fileDescriptions, setFileDescriptions] = useState<Record<string, string>>({});

    useEffect(() => {
        // Reset descriptions when the dialog is opened with new files
        if (isOpen) {
            setFileDescriptions({});
        }
    }, [isOpen]);

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
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle>Add Files to Project</DialogTitle>
                    <DialogDescription>
                        Add descriptions for each file. This helps the AI understand the file's purpose.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    {fileList.length > 0 ? (
                        <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-2">
                            {fileList.map((file, index) => (
                                <Card key={index} className="bg-muted/50">
                                    <CardContent className="p-3">
                                        <div className="flex items-center gap-3">
                                            <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-foreground truncate" title={file.name}>
                                                    {file.name}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {(file.size / 1024).toFixed(1)} KB
                                                </p>
                                            </div>
                                        </div>
                                        <Textarea
                                            placeholder={`Add a description for ${file.name} (optional)`}
                                            className="bg-background text-foreground placeholder:text-muted-foreground mt-2"
                                            rows={2}
                                            disabled={isSubmitting}
                                            value={fileDescriptions[file.name] || ""}
                                            onChange={e => handleFileDescriptionChange(file.name, e.target.value)}
                                        />
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <p className="text-muted-foreground">No files selected.</p>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
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
