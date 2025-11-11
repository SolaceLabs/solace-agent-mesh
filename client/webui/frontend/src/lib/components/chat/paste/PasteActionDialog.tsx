import React, { useState, useEffect } from "react";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
    Button,
    Input,
    Label,
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/lib/components/ui";

import { generateArtifactDescription } from "./pasteUtils";

interface PasteActionDialogProps {
    isOpen: boolean;
    content: string;
    onSaveAsArtifact: (title: string, type: string, description?: string) => Promise<void>;
    onCancel: () => void;
    existingArtifacts?: string[]; // List of existing artifact filenames
}

const FILE_TYPES = [
    { value: "auto", label: "Auto Detect Type" },
    { value: "text/plain", label: "Plain Text" },
    { value: "text/markdown", label: "Markdown" },
    { value: "application/json", label: "JSON" },
    { value: "text/html", label: "HTML" },
    { value: "text/css", label: "CSS" },
    { value: "text/javascript", label: "JavaScript" },
    { value: "text/typescript", label: "TypeScript" },
    { value: "text/python", label: "Python" },
    { value: "text/yaml", label: "YAML" },
    { value: "text/xml", label: "XML" },
];

// Helper function to detect file type from content
const detectFileType = (content: string): string => {
    // Check for common code patterns
    if (content.includes('def ') || content.includes('import ') && content.includes('from ')) {
        return 'text/python';
    }
    if (content.includes('function ') || content.includes('const ') || content.includes('let ') || content.includes('=>')) {
        return 'text/javascript';
    }
    if (content.includes('interface ') || content.includes('type ') && content.includes(':')) {
        return 'text/typescript';
    }
    if (content.includes('<!DOCTYPE') || content.includes('<html')) {
        return 'text/html';
    }
    if (content.includes('{') && content.includes('}') && content.includes(':')) {
        try {
            JSON.parse(content);
            return 'application/json';
        } catch {
            // Not valid JSON
        }
    }
    if (content.includes('---') && (content.includes('apiVersion:') || content.includes('kind:'))) {
        return 'text/yaml';
    }
    if (content.includes('<?xml') || content.includes('<') && content.includes('/>')) {
        return 'text/xml';
    }
    if (content.includes('#') && (content.includes('##') || content.includes('```'))) {
        return 'text/markdown';
    }
    return 'text/plain';
};

// Helper function to get file extension from MIME type
const getExtensionFromMimeType = (mimeType: string): string => {
    const extensionMap: Record<string, string> = {
        'text/plain': 'txt',
        'text/markdown': 'md',
        'application/json': 'json',
        'text/html': 'html',
        'text/css': 'css',
        'text/javascript': 'js',
        'text/typescript': 'ts',
        'text/python': 'py',
        'text/yaml': 'yaml',
        'text/xml': 'xml',
    };
    return extensionMap[mimeType] || 'txt';
};

export const PasteActionDialog: React.FC<PasteActionDialogProps> = ({
    isOpen,
    content,
    onSaveAsArtifact,
    onCancel,
    existingArtifacts = [],
}) => {
    const [title, setTitle] = useState("snippet.txt");
    const [description, setDescription] = useState("");
    const [fileType, setFileType] = useState("auto");
    const [isSaving, setIsSaving] = useState(false);
    const [userConfirmedOverwrite, setUserConfirmedOverwrite] = useState(false);
    
    // Check if current title exists in artifacts
    const titleExists = existingArtifacts.includes(title);
    // Show warning whenever title exists (even after confirmation)
    const showOverwriteWarning = titleExists;

    // Auto-detect file type and generate description when dialog opens
    useEffect(() => {
        if (isOpen && content) {
            const detectedType = detectFileType(content);
            setFileType(detectedType);
            // Update title with appropriate extension
            const extension = getExtensionFromMimeType(detectedType);
            setTitle(`snippet.${extension}`);
            // Generate and set description
            const generatedDescription = generateArtifactDescription(content);
            setDescription(generatedDescription);
        }
    }, [isOpen, content]);


    // Update title when file type changes
    useEffect(() => {
        if (fileType !== 'auto') {
            const extension = getExtensionFromMimeType(fileType);
            // Only update if the current title is still the default pattern
            if (title.startsWith('snippet.')) {
                setTitle(`snippet.${extension}`);
            }
        }
    }, [fileType, title]);
    
    // Reset confirmation when title changes
    useEffect(() => {
        setUserConfirmedOverwrite(false);
    }, [title]);


    const handleSaveArtifact = async () => {
        // Check if artifact already exists and user hasn't confirmed
        if (titleExists && !userConfirmedOverwrite) {
            // First click on duplicate name - show warning and require confirmation
            setUserConfirmedOverwrite(true);
            return;
        }
        
        // Either no conflict OR user has confirmed overwrite - proceed with save
        setIsSaving(true);
        try {
            await onSaveAsArtifact(title, fileType, description.trim() || undefined);
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
    };

    const charCount = content.length;
    const lineCount = content.split('\n').length;

    // Artifact form dialog - always shown now
    return (
        <Dialog open={isOpen} onOpenChange={handleCancel}>
            <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Create Artifact</DialogTitle>
                    <DialogDescription>
                        Save this text as an artifact that the agent can access
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="title">Filename</Label>
                        <Input
                            id="title"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="snippet.txt"
                            autoFocus={false}
                            onFocus={(e) => {
                                setTimeout(() => {
                                    e.target.setSelectionRange(e.target.value.length, e.target.value.length);
                                }, 0);
                            }}
                        />
                        {showOverwriteWarning && (
                            <p className="text-sm text-yellow-600 dark:text-yellow-500">
                                ⚠️ An artifact with this name already exists. {userConfirmedOverwrite ? "Click again to confirm overwrite." : "Saving will create a new version."}
                            </p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="description">Description (optional)</Label>
                        <Input
                            id="description"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Brief description of this artifact"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="type">Type</Label>
                        <Select value={fileType} onValueChange={setFileType}>
                            <SelectTrigger id="type">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {FILE_TYPES.map((type) => (
                                    <SelectItem key={type.value} value={type.value}>
                                        {type.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label>Content</Label>
                        <div className="rounded-md border bg-muted/30 p-4 max-h-60 overflow-auto">
                            <pre className="text-sm whitespace-pre-wrap break-words font-mono">
                                {content}
                            </pre>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {charCount} characters, {lineCount} lines
                        </p>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={handleCancel} disabled={isSaving}>
                        Cancel
                    </Button>
                    <Button onClick={handleSaveArtifact} disabled={isSaving || !title.trim()}>
                        {isSaving ? "Saving..." : (titleExists && userConfirmedOverwrite) ? "Overwrite & Save" : titleExists ? "Confirm Overwrite" : "Save Artifact"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};