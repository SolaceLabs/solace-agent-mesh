import React, { useState, useEffect } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, Button, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Textarea } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";

import { generateArtifactDescription } from "./pasteUtils";

interface PasteActionDialogProps {
    isOpen: boolean;
    content: string;
    onSaveAsArtifact: (title: string, type: string, content: string, description?: string) => Promise<void>;
    onCancel: () => void;
    existingArtifacts?: string[]; // List of existing artifact filenames
}

const FILE_TYPES = [
    { value: "auto", label: "Auto Detect Type" },
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

// Helper function to detect if content is CSV
const isCSV = (content: string): boolean => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return false;

    // Check if lines have consistent comma-separated values
    const firstLineCommas = (lines[0].match(/,/g) || []).length;
    if (firstLineCommas === 0) return false;

    // Check at least first 3 lines (or all if less) have similar comma count
    const linesToCheck = Math.min(lines.length, 5);
    for (let i = 1; i < linesToCheck; i++) {
        const commas = (lines[i].match(/,/g) || []).length;
        // Allow some variance but should be close to first line
        if (Math.abs(commas - firstLineCommas) > 1) return false;
    }

    return true;
};

// Helper function to detect file type from content
const detectFileType = (content: string): string => {
    // Check for CSV first (common paste format)
    if (isCSV(content)) {
        return "text/csv";
    }
    // Check for common code patterns
    if (content.includes("def ") || (content.includes("import ") && content.includes("from "))) {
        return "text/python";
    }
    if (content.includes("function ") || content.includes("const ") || content.includes("let ") || content.includes("=>")) {
        return "text/javascript";
    }
    if (content.includes("interface ") || (content.includes("type ") && content.includes(":"))) {
        return "text/typescript";
    }
    if (content.includes("<!DOCTYPE") || content.includes("<html")) {
        return "text/html";
    }
    if (content.includes("{") && content.includes("}") && content.includes(":")) {
        try {
            JSON.parse(content);
            return "application/json";
        } catch {
            // Not valid JSON
        }
    }
    if (content.includes("---") && (content.includes("apiVersion:") || content.includes("kind:"))) {
        return "text/yaml";
    }
    if (content.includes("<?xml") || (content.includes("<") && content.includes("/>"))) {
        return "text/xml";
    }
    if (content.includes("#") && (content.includes("##") || content.includes("```"))) {
        return "text/markdown";
    }
    return "text/plain";
};

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

export const PasteActionDialog: React.FC<PasteActionDialogProps> = ({ isOpen, content, onSaveAsArtifact, onCancel, existingArtifacts = [] }) => {
    const [title, setTitle] = useState("snippet.txt");
    const [description, setDescription] = useState("");
    const [fileType, setFileType] = useState("auto");
    const [isSaving, setIsSaving] = useState(false);
    const [userConfirmedOverwrite, setUserConfirmedOverwrite] = useState(false);
    const [editableContent, setEditableContent] = useState("");
    const [contentError, setContentError] = useState<string | null>(null);

    // Check if current title exists in artifacts
    const titleExists = existingArtifacts.includes(title);
    // Show warning whenever title exists (even after confirmation)
    const showOverwriteWarning = titleExists;

    // Auto-detect file type and generate description when dialog opens
    useEffect(() => {
        if (isOpen && content) {
            setEditableContent(content);
            const detectedType = detectFileType(content);
            setFileType(detectedType);
            // Update title with appropriate extension, ensuring uniqueness
            const extension = getExtensionFromMimeType(detectedType);
            const uniqueFilename = generateUniqueFilename("snippet", extension, existingArtifacts);
            setTitle(uniqueFilename);
            // Generate and set description
            const generatedDescription = generateArtifactDescription(content);
            setDescription(generatedDescription);
        }
    }, [isOpen, content, existingArtifacts]);

    // Update title when file type changes
    useEffect(() => {
        if (fileType !== "auto") {
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
        }
    }, [fileType, title]);

    // Reset confirmation when title changes
    useEffect(() => {
        setUserConfirmedOverwrite(false);
    }, [title]);

    const handleSaveArtifact = async () => {
        // Check if content is empty
        if (!editableContent.trim()) {
            setContentError("Content cannot be empty. Please add some content before saving.");
            return;
        }

        // Clear any previous error
        setContentError(null);

        // Check if artifact already exists and user hasn't confirmed
        if (titleExists && !userConfirmedOverwrite) {
            // First click on duplicate name - show warning and require confirmation
            setUserConfirmedOverwrite(true);
            return;
        }

        // Either no conflict OR user has confirmed overwrite - proceed with save
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

    const handleCancel = () => {
        resetForm();
        onCancel();
    };

    const resetForm = () => {
        setTitle("snippet.txt");
        setDescription("");
        setFileType("auto");
        setIsSaving(false);
        setUserConfirmedOverwrite(false);
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
                        {showOverwriteWarning && (
                            <p className="text-sm text-yellow-600 dark:text-yellow-500">⚠️ A file with this name already exists. {userConfirmedOverwrite ? "Click again to confirm overwrite." : "Saving will create a new version."}</p>
                        )}
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
                        {isSaving ? "Saving..." : titleExists && userConfirmedOverwrite ? "Overwrite & Save" : titleExists ? "Confirm Overwrite" : "Save File"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
