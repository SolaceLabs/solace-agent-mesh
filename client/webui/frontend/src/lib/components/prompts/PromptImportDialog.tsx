import React, { useState, useRef } from "react";
import { CheckCircle, FileJson } from "lucide-react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Button, Input, Label } from "@/lib/components/ui";
import { Alert, AlertDescription } from "@/lib/components/ui/alert";
import { MessageBanner } from "@/lib/components";

interface PromptImportData {
    version: string;
    exportedAt: number;
    prompt: {
        name: string;
        description?: string;
        category?: string;
        command?: string;
        promptText: string;
        metadata?: {
            authorName?: string;
            originalVersion: number;
            originalCreatedAt: number;
        };
    };
}

interface PromptImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (data: PromptImportData, options: { preserveCommand: boolean; preserveCategory: boolean }) => Promise<void>;
}

export const PromptImportDialog: React.FC<PromptImportDialogProps> = ({ open, onOpenChange, onImport }) => {
    const [importData, setImportData] = useState<PromptImportData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [validationErrors, setValidationErrors] = useState<string[]>([]);
    const [isImporting, setIsImporting] = useState(false);
    const [editedCommand, setEditedCommand] = useState<string>("");
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFileName, setSelectedFileName] = useState<string>("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (!selectedFile) return;

        setError(null);
        setValidationErrors([]);
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

            // Currently only version 1.0 is supported. Future versions may require migration logic.
            // TODO: Consider implementing version migration strategies if format changes are needed
            if (data.version !== "1.0") {
                setError(`Unsupported export format version: ${data.version}. Only version 1.0 is currently supported.`);
                return;
            }

            if (!data.prompt.name || !data.prompt.promptText) {
                setError("Invalid export format: missing prompt name or text");
                return;
            }

            // Validate field lengths to match backend constraints
            const validationErrors: string[] = [];

            if (data.prompt.name.length > 255) {
                validationErrors.push(`Name is too long (${data.prompt.name.length} characters, max 255)`);
            }

            if (data.prompt.description && data.prompt.description.length > 500) {
                validationErrors.push(`Description is too long (${data.prompt.description.length} characters, max 500)`);
            }

            if (data.prompt.category && data.prompt.category.length > 100) {
                validationErrors.push(`Category is too long (${data.prompt.category.length} characters, max 100)`);
            }

            if (data.prompt.command && data.prompt.command.length > 50) {
                validationErrors.push(`Command is too long (${data.prompt.command.length} characters, max 50)`);
            }

            if (data.prompt.metadata?.authorName && data.prompt.metadata.authorName.length > 255) {
                validationErrors.push(`Author name is too long (${data.prompt.metadata.authorName.length} characters, max 255)`);
            }

            if (validationErrors.length > 0) {
                setValidationErrors(validationErrors);
                setError("The imported prompt has fields that exceed maximum length limits:");
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
                target: { files, value: "" },
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
                preserveCommand: !!editedCommand,
                preserveCategory: true, // Always preserve category
            });

            // Reset state and close dialog
            setImportData(null);
            setSelectedFileName("");
            setEditedCommand("");
            setError(null);
            setValidationErrors([]);
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
            setValidationErrors([]);
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
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Import Prompt</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 overflow-x-hidden py-4">
                    {/* File Upload - Drag and Drop or Selected File Display */}
                    {!selectedFileName ? (
                        <div
                            className={`flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center transition-all ${
                                isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/30"
                            }`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={handleUploadClick}
                        >
                            <FileJson className={`mb-3 h-10 w-10 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                            <p className={`mb-1 text-sm font-medium transition-colors ${isDragging ? "text-primary" : "text-foreground"}`}>{isDragging ? "Drop JSON file here" : "Drag and drop JSON file here"}</p>
                            <p className="text-muted-foreground text-xs">or click to browse</p>
                            <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".json" disabled={isImporting} className="hidden" />
                        </div>
                    ) : (
                        <div className="bg-muted/30 flex items-center gap-3 rounded-md border p-4">
                            <FileJson className="text-primary h-5 w-5 flex-shrink-0" />
                            <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium">{selectedFileName}</p>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setSelectedFileName("");
                                    setImportData(null);
                                    setEditedCommand("");
                                    setError(null);
                                    setValidationErrors([]);
                                }}
                                disabled={isImporting}
                            >
                                Change
                            </Button>
                        </div>
                    )}

                    {/* Error Display */}
                    {error && (
                        <div className="space-y-2">
                            <MessageBanner variant="error" message={error} />
                            {validationErrors.length > 0 && (
                                <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950/30">
                                    <ul className="list-inside list-disc space-y-1 text-sm text-red-800 dark:text-red-200">
                                        {validationErrors.map((err, idx) => (
                                            <li key={idx}>{err}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Preview */}
                    {importData && !error && (
                        <div className="space-y-4">
                            <Alert>
                                <CheckCircle className="h-4 w-4" />
                                <AlertDescription>File validated successfully. Review the details below:</AlertDescription>
                            </Alert>

                            <div className="space-y-3 overflow-hidden rounded-lg border p-4">
                                <div>
                                    <Label className="text-muted-foreground text-xs">Name</Label>
                                    <p className="overflow-wrap-anywhere font-medium break-words">{importData.prompt.name}</p>
                                </div>

                                {importData.prompt.description && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Description</Label>
                                        <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.description}</p>
                                    </div>
                                )}

                                {importData.prompt.category && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Category</Label>
                                        <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.category}</p>
                                    </div>
                                )}

                                {importData.prompt.command && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Command</Label>
                                        <p className="font-mono text-sm break-all">{importData.prompt.command}</p>
                                    </div>
                                )}

                                {importData.prompt.metadata?.authorName && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Original Author</Label>
                                        <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.metadata.authorName}</p>
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
                                            <span className="text-muted-foreground text-sm">/</span>
                                            <Input id="import-command" value={editedCommand} onChange={e => handleCommandChange(e.target.value)} placeholder="e.g., code-review" className="flex-1" />
                                        </div>
                                        <p className="text-muted-foreground text-xs">You can modify the shortcut if needed. If it conflicts with an existing shortcut, a unique one will be generated automatically.</p>
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
