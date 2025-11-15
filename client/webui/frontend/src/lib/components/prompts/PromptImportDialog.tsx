import React, { useState, useRef } from "react";
import { CheckCircle, FileJson } from "lucide-react";

import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    Button,
    Input,
    Label,
} from "@/lib/components/ui";
import { Alert, AlertDescription } from "@/lib/components/ui/alert";
import { MessageBanner } from "@/lib/components";

interface PromptImportData {
    version: string;
    exported_at: number;
    prompt: {
        name: string;
        description?: string;
        category?: string;
        command?: string;
        prompt_text: string;
        metadata?: {
            author_name?: string;
            original_version: number;
            original_created_at: number;
        };
    };
}

interface PromptImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (data: PromptImportData, options: { preserve_command: boolean; preserve_category: boolean }) => Promise<void>;
}

export const PromptImportDialog: React.FC<PromptImportDialogProps> = ({ open, onOpenChange, onImport }) => {
    const [importData, setImportData] = useState<PromptImportData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isImporting, setIsImporting] = useState(false);
    const [editedCommand, setEditedCommand] = useState<string>("");
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFileName, setSelectedFileName] = useState<string>("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (!selectedFile) return;

        setError(null);
        setImportData(null);

        // Validate file type
        if (!selectedFile.name.endsWith(".json")) {
            setError("Please select a JSON file");
            return;
        }

        // Validate file size (1MB limit)
        if (selectedFile.size > 1024 * 1024) {
            setError("File size must be less than 1MB");
            return;
        }

        try {
            const text = await selectedFile.text();
            const data = JSON.parse(text) as PromptImportData;

            // Validate format
            if (!data.version || !data.prompt) {
                setError("Invalid export format: missing required fields");
                return;
            }

            if (data.version !== "1.0") {
                setError(`Unsupported export format version: ${data.version}`);
                return;
            }

            if (!data.prompt.name || !data.prompt.prompt_text) {
                setError("Invalid export format: missing prompt name or text");
                return;
            }

            setImportData(data);
            setSelectedFileName(selectedFile.name);
            // Initialize edited command with the imported command
            setEditedCommand(data.prompt.command || "");
        } catch {
            setError("Failed to parse JSON file. Please ensure it's a valid prompt export.");
        }
        // Reset file input
        if (e.target) {
            e.target.value = "";
        }
    };

    const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragging(false);
    };

    const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragging(false);

        const files = event.dataTransfer.files;
        if (files && files.length > 0) {
            // Simulate file input change event
            const fakeEvent = {
                target: { files, value: "" }
            } as React.ChangeEvent<HTMLInputElement>;
            handleFileChange(fakeEvent);
        }
    };

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const handleImport = async () => {
        // Validate that a file has been selected
        if (!importData) {
            setError("Please select a JSON file to import");
            return;
        }

        setIsImporting(true);
        setError(null);

        try {
            // Update the import data with the edited command
            const updatedImportData = {
                ...importData,
                prompt: {
                    ...importData.prompt,
                    command: editedCommand || undefined,
                },
            };

            await onImport(updatedImportData, {
                preserve_command: !!editedCommand,
                preserve_category: true, // Always preserve category
            });

            // Reset state and close dialog
            setImportData(null);
            setSelectedFileName("");
            setEditedCommand("");
            setError(null);
            onOpenChange(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to import prompt");
        } finally {
            setIsImporting(false);
        }
    };

    const handleClose = () => {
        if (!isImporting) {
            setImportData(null);
            setSelectedFileName("");
            setEditedCommand("");
            setError(null);
            onOpenChange(false);
        }
    };

    // Check for command conflicts (this is a simple check - backend will handle the actual conflict resolution)
    const handleCommandChange = (value: string) => {
        setEditedCommand(value);
        // You could add API call here to check for conflicts in real-time if needed
        // For now, we'll let the backend handle it and show warnings in the response
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Import Prompt</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* File Upload - Drag and Drop or Selected File Display */}
                    {!selectedFileName ? (
                        <div
                            className={`flex flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center transition-all cursor-pointer ${
                                isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/30"
                            }`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={handleUploadClick}
                        >
                            <FileJson className={`mb-3 h-10 w-10 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                            <p className={`mb-1 text-sm font-medium transition-colors ${isDragging ? "text-primary" : "text-foreground"}`}>
                                {isDragging ? "Drop JSON file here" : "Drag and drop JSON file here"}
                            </p>
                            <p className="text-muted-foreground text-xs">or click to browse</p>
                            <input
                                type="file"
                                ref={fileInputRef}
                                onChange={handleFileChange}
                                accept=".json"
                                disabled={isImporting}
                                className="hidden"
                            />
                        </div>
                    ) : (
                        <div className="flex items-center gap-3 rounded-md border p-4 bg-muted/30">
                            <FileJson className="h-5 w-5 text-primary flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{selectedFileName}</p>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setSelectedFileName("");
                                    setImportData(null);
                                    setEditedCommand("");
                                    setError(null);
                                }}
                                disabled={isImporting}
                            >
                                Change
                            </Button>
                        </div>
                    )}

                    {/* Error Display */}
                    {error && (
                        <MessageBanner
                            variant="error"
                            message={error}
                        />
                    )}

                    {/* Preview */}
                    {importData && !error && (
                        <div className="space-y-4">
                            <Alert>
                                <CheckCircle className="h-4 w-4" />
                                <AlertDescription>File validated successfully. Review the details below:</AlertDescription>
                            </Alert>

                            <div className="rounded-lg border p-4 space-y-3">
                                <div>
                                    <Label className="text-xs text-muted-foreground">Name</Label>
                                    <p className="font-medium">{importData.prompt.name}</p>
                                </div>

                                {importData.prompt.description && (
                                    <div>
                                        <Label className="text-xs text-muted-foreground">Description</Label>
                                        <p className="text-sm">{importData.prompt.description}</p>
                                    </div>
                                )}

                                {importData.prompt.category && (
                                    <div>
                                        <Label className="text-xs text-muted-foreground">Category</Label>
                                        <p className="text-sm">{importData.prompt.category}</p>
                                    </div>
                                )}

                                {importData.prompt.command && (
                                    <div>
                                        <Label className="text-xs text-muted-foreground">Command</Label>
                                        <p className="text-sm font-mono">/{importData.prompt.command}</p>
                                    </div>
                                )}

                                {importData.prompt.metadata?.author_name && (
                                    <div>
                                        <Label className="text-xs text-muted-foreground">Original Author</Label>
                                        <p className="text-sm">{importData.prompt.metadata.author_name}</p>
                                    </div>
                                )}
                            </div>

                            {/* Import Options */}
                            <div className="space-y-3 rounded-lg border p-4">
                                <Label className="text-sm font-medium">Import Options</Label>

                                {/* Editable Command Field */}
                                {importData.prompt.command && (
                                    <div className="space-y-2">
                                        <Label htmlFor="import-command" className="text-sm">
                                            Chat Shortcut
                                        </Label>
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-muted-foreground">/</span>
                                            <Input
                                                id="import-command"
                                                value={editedCommand}
                                                onChange={(e) => handleCommandChange(e.target.value)}
                                                placeholder="e.g., code-review"
                                                className="flex-1"
                                            />
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            You can modify the shortcut if needed. If it conflicts with an existing shortcut, a unique one will be generated automatically.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleClose} disabled={isImporting}>
                        Cancel
                    </Button>
                    <Button onClick={handleImport} disabled={isImporting}>
                        {isImporting ? "Importing..." : "Import"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};