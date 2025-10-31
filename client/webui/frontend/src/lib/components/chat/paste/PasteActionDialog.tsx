import React, { useState, useEffect } from "react";
import { FileText, Save } from "lucide-react";

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

interface PasteActionDialogProps {
    isOpen: boolean;
    content: string;
    onPasteAsText: () => void;
    onSaveAsArtifact: (title: string, type: string) => Promise<void>;
    onCancel: () => void;
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
    onPasteAsText,
    onSaveAsArtifact,
    onCancel,
}) => {
    const [showArtifactForm, setShowArtifactForm] = useState(false);
    const [title, setTitle] = useState("snippet.txt");
    const [fileType, setFileType] = useState("auto");
    const [isSaving, setIsSaving] = useState(false);

    // Auto-detect file type when form is shown
    useEffect(() => {
        if (showArtifactForm && content) {
            const detectedType = detectFileType(content);
            setFileType(detectedType);
            // Update title with appropriate extension
            const extension = getExtensionFromMimeType(detectedType);
            setTitle(`snippet.${extension}`);
        }
    }, [showArtifactForm, content]);

    // Update title when file type changes
    useEffect(() => {
        if (fileType !== 'auto') {
            const extension = getExtensionFromMimeType(fileType);
            // Only update if the current title is still the default pattern
            if (title.startsWith('snippet.')) {
                setTitle(`snippet.${extension}`);
            }
        }
    }, [fileType]);

    const handlePasteAsText = () => {
        onPasteAsText();
        resetForm();
    };

    const handleShowArtifactForm = () => {
        setShowArtifactForm(true);
    };

    const handleSaveArtifact = async () => {
        setIsSaving(true);
        try {
            await onSaveAsArtifact(title, fileType);
            resetForm();
        } catch (error) {
            console.error("Error saving artifact:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleCancel = () => {
        resetForm();
        onCancel();
    };

    const resetForm = () => {
        setShowArtifactForm(false);
        setTitle("snippet.txt");
        setFileType("auto");
        setIsSaving(false);
    };

    const charCount = content.length;
    const lineCount = content.split('\n').length;

    if (!showArtifactForm) {
        // Initial choice dialog
        return (
            <Dialog open={isOpen} onOpenChange={handleCancel}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>What would you like to do with this text?</DialogTitle>
                        <DialogDescription>
                            {charCount} characters, {lineCount} lines
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex flex-col gap-3 py-4">
                        <Button
                            variant="outline"
                            className="h-auto flex-col items-start gap-2 p-4"
                            onClick={handlePasteAsText}
                        >
                            <div className="flex items-center gap-2">
                                <FileText className="size-5" />
                                <span className="font-semibold">Paste as Text</span>
                            </div>
                            <span className="text-sm text-muted-foreground">
                                Include in your next message
                            </span>
                        </Button>

                        <Button
                            variant="outline"
                            className="h-auto flex-col items-start gap-2 p-4"
                            onClick={handleShowArtifactForm}
                        >
                            <div className="flex items-center gap-2">
                                <Save className="size-5" />
                                <span className="font-semibold">Save as Artifact</span>
                            </div>
                            <span className="text-sm text-muted-foreground">
                                Save for agent to access and reference
                            </span>
                        </Button>
                    </div>

                    <DialogFooter>
                        <Button variant="ghost" onClick={handleCancel}>
                            Cancel
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        );
    }

    // Artifact form dialog
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
                        <Label htmlFor="title">Title (optional)</Label>
                        <Input
                            id="title"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="snippet.txt"
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
                        {isSaving ? "Saving..." : "Save Artifact"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};