import React, { useState, useEffect } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, Button, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Textarea } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";

import { generateArtifactDescription } from "./pasteUtils";

export interface PasteMetadata {
    filename: string;
    mimeType: string;
    description?: string;
    content: string;
}

interface PasteActionDialogProps {
    isOpen: boolean;
    content: string;
    onSaveMetadata: (metadata: PasteMetadata) => void; // Just saves metadata locally, no upload
    onCancel: () => void;
    existingArtifacts?: string[]; // List of existing artifact filenames
    // Initial values from previously configured metadata
    initialFilename?: string;
    initialMimeType?: string;
    initialDescription?: string;
    // Default filename to use when not configured (computed by parent to account for other pending items)
    defaultFilename?: string;
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

export const PasteActionDialog: React.FC<PasteActionDialogProps> = ({ isOpen, content, onSaveMetadata, onCancel, existingArtifacts = [], initialFilename, initialMimeType, initialDescription, defaultFilename }) => {
    const [title, setTitle] = useState("snippet.txt");
    const [description, setDescription] = useState("");
    const [fileType, setFileType] = useState(DEFAULT_MIME_TYPE);
    const [editableContent, setEditableContent] = useState("");
    const [contentError, setContentError] = useState<string | null>(null);

    // Check if current title exists in artifacts (but not if it's the same as initial - user is editing)
    const titleExists = existingArtifacts.includes(title) && title !== initialFilename;
    // Show warning whenever title exists
    const showOverwriteWarning = titleExists;

    // Initialize form when dialog opens
    useEffect(() => {
        if (isOpen && content) {
            setEditableContent(content);

            // If we have initial values (user is re-editing), use them
            if (initialFilename) {
                setTitle(initialFilename);
                setFileType(initialMimeType || DEFAULT_MIME_TYPE);
                setDescription(initialDescription || "");
            } else {
                // First time opening - use the pre-computed default filename if provided,
                // otherwise generate one (fallback for backwards compatibility)
                setFileType(DEFAULT_MIME_TYPE);
                const uniqueFilename = defaultFilename || generateUniqueFilename("snippet", "txt", existingArtifacts);
                setTitle(uniqueFilename);
                const generatedDescription = generateArtifactDescription(content);
                setDescription(generatedDescription);
            }
        }
    }, [isOpen, content, existingArtifacts, initialFilename, initialMimeType, initialDescription, defaultFilename]);

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

    const handleSaveMetadata = () => {
        // Check if content is empty
        if (!editableContent.trim()) {
            setContentError("Content cannot be empty. Please add some content before saving.");
            return;
        }

        // Clear any previous error
        setContentError(null);

        // Save metadata locally (no upload yet)
        onSaveMetadata({
            filename: title,
            mimeType: fileType,
            description: description.trim() || undefined,
            content: editableContent,
        });

        resetForm();
    };

    const handleCancel = () => {
        resetForm();
        onCancel();
    };

    const resetForm = () => {
        setTitle("snippet.txt");
        setDescription("");
        setFileType(DEFAULT_MIME_TYPE);
        setEditableContent("");
        setContentError(null);
    };

    const charCount = editableContent.length;
    const lineCount = editableContent.split("\n").length;

    // Artifact form dialog - always shown now
    return (
        <Dialog open={isOpen} onOpenChange={handleCancel}>
            <DialogContent className="flex max-h-[80vh] flex-col sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Customize File</DialogTitle>
                    <DialogDescription>Customize the file settings before sending to the agent</DialogDescription>
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
                        {showOverwriteWarning && <MessageBanner variant="warning" message="A file with this name already exists. Saving will create a new version." />}
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
                        <Label htmlFor="content">Content</Label>
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
                            className="min-h-[300px] resize-y font-mono text-sm"
                            placeholder="Paste content here..."
                        />
                        <p className="text-muted-foreground text-xs">
                            {charCount} characters, {lineCount} lines
                        </p>
                        {contentError && <MessageBanner variant="error" message={contentError} dismissible onDismiss={() => setContentError(null)} />}
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={handleCancel}>
                        Cancel
                    </Button>
                    <Button onClick={handleSaveMetadata} disabled={!title.trim()}>
                        Customize
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
