import React, { useState, useEffect } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, Button, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Textarea } from "@/lib/components/ui";
import { MessageBanner, ConfirmationDialog } from "@/lib/components/common";

import { generateArtifactDescription } from "./pasteUtils";

interface PasteActionDialogProps {
    isOpen: boolean;
    content: string;
    onSaveAsArtifact: (title: string, type: string, content: string, description?: string) => Promise<void>;
    onCancel: () => void;
    existingArtifacts?: string[]; // List of existing artifact filenames
}

const FILE_TYPES = [
    { value: "text/plain", label: "Plain Text" },
    { value: "text/markdown", label: "Markdown" },
    { value: "text/csv", label: "CSV" },
    { value: "application/json", label: "JSON" },
    { value: "text/html", label: "HTML" },
    { value: "text/css", label: "CSS" },
    { value: "text/javascript", label: "JavaScript" },
    { value: "text/typescript", label: "TypeScript" },
    { value: "text/python", label: "Python" },
    { value: "text/yaml", label: "YAML" },
    { value: "text/xml", label: "XML" },
];

// Helper function to get file extension from MIME type
const getExtensionFromMimeType = (mimeType: string): string => {
    const extensionMap: Record<string, string> = {
        "text/plain": "txt",
        "text/markdown": "md",
        "text/csv": "csv",
        "application/json": "json",
        "text/html": "html",
        "text/css": "css",
        "text/javascript": "js",
        "text/typescript": "ts",
        "text/python": "py",
        "text/yaml": "yaml",
        "text/xml": "xml",
    };
    return extensionMap[mimeType] || "txt";
};

// Helper function to generate a unique filename
const generateUniqueFilename = (baseName: string, extension: string, existingArtifacts: string[]): string => {
    const filename = `${baseName}.${extension}`;

    // If the filename doesn't exist, return it as is
    if (!existingArtifacts.includes(filename)) {
        return filename;
    }

    // Find the next available number
    let counter = 2;
    while (existingArtifacts.includes(`${baseName}-${counter}.${extension}`)) {
        counter++;
    }

    return `${baseName}-${counter}.${extension}`;
};

// Default MIME type - always use text/plain for safety and readability
const DEFAULT_MIME_TYPE = "text/plain";

export const PasteActionDialog: React.FC<PasteActionDialogProps> = ({ isOpen, content, onSaveAsArtifact, onCancel, existingArtifacts = [] }) => {
    const [title, setTitle] = useState("snippet.txt");
    const [description, setDescription] = useState("");
    const [fileType, setFileType] = useState(DEFAULT_MIME_TYPE);
    const [isSaving, setIsSaving] = useState(false);
    const [editableContent, setEditableContent] = useState("");
    const [contentError, setContentError] = useState<string | null>(null);
    const [showOverwriteConfirmDialog, setShowOverwriteConfirmDialog] = useState(false);

    // Check if current title exists in artifacts
    const titleExists = existingArtifacts.includes(title);
    // Show warning whenever title exists
    const showOverwriteWarning = titleExists;

    // Initialize form when dialog opens - always default to text/plain for safety
    useEffect(() => {
        if (isOpen && content) {
            setEditableContent(content);
            // Always default to text/plain - user can change if needed
            setFileType(DEFAULT_MIME_TYPE);
            // Update title with .txt extension, ensuring uniqueness
            const uniqueFilename = generateUniqueFilename("snippet", "txt", existingArtifacts);
            setTitle(uniqueFilename);
            // Generate and set description
            const generatedDescription = generateArtifactDescription(content);
            setDescription(generatedDescription);
        }
    }, [isOpen, content, existingArtifacts]);

    // Update title extension when user explicitly changes file type
    useEffect(() => {
        const extension = getExtensionFromMimeType(fileType);
        // Only update if the current title is still the default pattern (snippet or snippet-N)
        if (title.match(/^snippet(-\d+)?\.[\w]+$/)) {
            // Extract the base name (snippet or snippet-N)
            const baseMatch = title.match(/^(snippet(-\d+)?)\./);
            const baseName = baseMatch ? baseMatch[1] : "snippet";
            const newFilename = `${baseName}.${extension}`;
            // Only change if the new filename is different
            if (newFilename !== title) {
                setTitle(newFilename);
            }
        }
    }, [fileType, title]);

    const handleSaveArtifact = async () => {
        // Check if content is empty
        if (!editableContent.trim()) {
            setContentError("Content cannot be empty. Please add some content before saving.");
            return;
        }

        // Clear any previous error
        setContentError(null);

        // Check if artifact already exists - show confirmation dialog
        if (titleExists) {
            setShowOverwriteConfirmDialog(true);
            return;
        }

        // No conflict - proceed with save
        await performSave();
    };

    const performSave = async () => {
        setIsSaving(true);
        try {
            await onSaveAsArtifact(title, fileType, editableContent, description.trim() || undefined);
            resetForm();
        } catch (error) {
            console.error("Error saving artifact:", error);
            // Don't reset form on error so user can try again
        } finally {
            setIsSaving(false);
        }
    };

    const handleConfirmOverwrite = async () => {
        setShowOverwriteConfirmDialog(false);
        await performSave();
    };

    const handleCancel = () => {
        resetForm();
        onCancel();
    };

    const resetForm = () => {
        setTitle("snippet.txt");
        setDescription("");
        setFileType(DEFAULT_MIME_TYPE);
        setIsSaving(false);
        setEditableContent("");
        setContentError(null);
        setShowOverwriteConfirmDialog(false);
    };

    const charCount = editableContent.length;
    const lineCount = editableContent.split("\n").length;

    // Artifact form dialog - always shown now
    return (
        <Dialog open={isOpen} onOpenChange={handleCancel}>
            <DialogContent className="flex max-h-[80vh] flex-col sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Create File</DialogTitle>
                    <DialogDescription>Save this text as a file that the agent can access</DialogDescription>
                </DialogHeader>

                <div className="flex-1 space-y-4 overflow-y-auto py-4">
                    <div className="space-y-2">
                        <Label htmlFor="title">Filename</Label>
                        <Input
                            id="title"
                            value={title}
                            onChange={e => setTitle(e.target.value)}
                            placeholder="snippet.txt"
                            autoFocus={false}
                            onFocus={e => {
                                setTimeout(() => {
                                    e.target.setSelectionRange(e.target.value.length, e.target.value.length);
                                }, 0);
                            }}
                        />
                        {showOverwriteWarning && <p className="text-sm text-yellow-600 dark:text-yellow-500">⚠️ A file with this name already exists. Saving will create a new version.</p>}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="description">Description (optional)</Label>
                        <Input id="description" value={description} onChange={e => setDescription(e.target.value)} placeholder="Brief description of this file" />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="type">Type</Label>
                        <Select value={fileType} onValueChange={setFileType}>
                            <SelectTrigger id="type">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {FILE_TYPES.map(type => (
                                    <SelectItem key={type.value} value={type.value}>
                                        {type.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="content">Content (editable)</Label>
                        <Textarea
                            id="content"
                            value={editableContent}
                            onChange={e => {
                                setEditableContent(e.target.value);
                                // Clear error when user starts typing
                                if (e.target.value.trim() && contentError) {
                                    setContentError(null);
                                }
                            }}
                            className="max-h-[300px] min-h-[200px] resize-none font-mono text-sm"
                            placeholder="Paste content here..."
                        />
                        <p className="text-muted-foreground text-xs">
                            {charCount} characters, {lineCount} lines
                        </p>
                        {contentError && <MessageBanner variant="error" message={contentError} dismissible onDismiss={() => setContentError(null)} />}
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={handleCancel} disabled={isSaving}>
                        Cancel
                    </Button>
                    <Button onClick={handleSaveArtifact} disabled={isSaving || !title.trim()}>
                        Save File
                    </Button>
                </DialogFooter>
            </DialogContent>

            {/* Overwrite Confirmation Dialog */}
            <ConfirmationDialog
                open={showOverwriteConfirmDialog}
                title="Overwrite existing file?"
                description={`A file named "${title}" already exists. This will create a new version of the file. The previous version will still be accessible.`}
                actionLabels={{ cancel: "Cancel", confirm: "Overwrite" }}
                onOpenChange={setShowOverwriteConfirmDialog}
                onConfirm={handleConfirmOverwrite}
            />
        </Dialog>
    );
};
