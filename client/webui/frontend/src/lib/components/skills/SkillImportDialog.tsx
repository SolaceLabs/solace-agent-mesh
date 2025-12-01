import React, { useState, useRef } from "react";
import { CheckCircle, FileText, Archive, FolderTree } from "lucide-react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Button, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { Alert, AlertDescription } from "@/lib/components/ui/alert";
import { MessageBanner } from "@/lib/components";

interface SkillImportData {
    name: string;
    description: string;
    summary?: string;
    involvedAgents?: string[];
    markdownContent?: string;
    isZip?: boolean;
    referencesCount?: number;
    scriptsCount?: number;
    assetsCount?: number;
}

interface SkillImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (file: File, options: { scope: string; ownerAgent?: string }) => Promise<void>;
}

export const SkillImportDialog: React.FC<SkillImportDialogProps> = ({ open, onOpenChange, onImport }) => {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewData, setPreviewData] = useState<SkillImportData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isImporting, setIsImporting] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [scope, setScope] = useState<string>("user");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const parseSkillMarkdown = (content: string): SkillImportData => {
        // Parse YAML frontmatter
        const frontmatterMatch = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);

        if (!frontmatterMatch) {
            throw new Error("Invalid skill format: missing YAML frontmatter (---)");
        }

        const frontmatterStr = frontmatterMatch[1];
        const markdownBody = frontmatterMatch[2].trim();

        // Simple YAML parsing for common fields
        const lines = frontmatterStr.split("\n");
        const data: Record<string, string | string[]> = {};
        let currentKey = "";
        let inArray = false;
        const arrayValues: string[] = [];

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            if (trimmed.startsWith("- ") && inArray) {
                arrayValues.push(trimmed.substring(2).trim());
            } else if (trimmed.includes(":")) {
                if (inArray && currentKey) {
                    data[currentKey] = [...arrayValues];
                    arrayValues.length = 0;
                }

                const colonIndex = trimmed.indexOf(":");
                const key = trimmed.substring(0, colonIndex).trim();
                const value = trimmed.substring(colonIndex + 1).trim();

                if (value === "") {
                    // Could be start of array
                    currentKey = key;
                    inArray = true;
                } else {
                    data[key] = value;
                    inArray = false;
                }
            }
        }

        if (inArray && currentKey) {
            data[currentKey] = [...arrayValues];
        }

        if (!data.name) {
            throw new Error("Missing required field: name");
        }
        if (!data.description) {
            throw new Error("Missing required field: description");
        }

        return {
            name: data.name as string,
            description: data.description as string,
            summary: data.summary as string | undefined,
            involvedAgents: Array.isArray(data.involved_agents) ? data.involved_agents : undefined,
            markdownContent: markdownBody,
        };
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setError(null);
        setPreviewData(null);

        // Validate file type
        const isZip = file.name.endsWith(".zip");
        const isMarkdown = file.name.endsWith(".SKILL.md") || file.name.endsWith(".md");
        const isJson = file.name.endsWith(".json");

        if (!isZip && !isMarkdown && !isJson) {
            setError("Please select a .zip, .SKILL.md, or .json file");
            return;
        }

        // Validate file size (10MB limit for ZIP, 1MB for others)
        const maxSize = isZip ? 10 * 1024 * 1024 : 1024 * 1024;
        if (file.size > maxSize) {
            setError(`File size must be less than ${isZip ? "10MB" : "1MB"}`);
            return;
        }

        try {
            if (isZip) {
                // For ZIP files, we can't fully parse in browser, but we can show basic info
                // The actual parsing happens on the server
                setPreviewData({
                    name: file.name.replace(/\.skill\.zip$/i, "").replace(/\.zip$/i, ""),
                    description: "Skill package (will be parsed on import)",
                    isZip: true,
                });
                setSelectedFile(file);
            } else {
                const text = await file.text();

                if (isMarkdown) {
                    const data = parseSkillMarkdown(text);
                    setPreviewData(data);
                } else {
                    // JSON format
                    const jsonData = JSON.parse(text);
                    if (!jsonData.skill) {
                        setError("Invalid export format: missing 'skill' field");
                        return;
                    }
                    setPreviewData({
                        name: jsonData.skill.name,
                        description: jsonData.skill.description,
                        involvedAgents: jsonData.skill.agent_chain?.map((n: { agent_name: string }) => n.agent_name),
                    });
                }

                setSelectedFile(file);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to parse file");
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
        if (!selectedFile) {
            setError("Please select a file to import");
            return;
        }

        setIsImporting(true);
        setError(null);

        try {
            await onImport(selectedFile, {
                scope,
                ownerAgent: previewData?.involvedAgents?.[0],
            });

            // Reset state and close dialog
            setSelectedFile(null);
            setPreviewData(null);
            setError(null);
            setScope("user");
            onOpenChange(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to import skill");
        } finally {
            setIsImporting(false);
        }
    };

    const handleClose = () => {
        if (!isImporting) {
            setSelectedFile(null);
            setPreviewData(null);
            setError(null);
            setScope("user");
            onOpenChange(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Import Skill</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* File Upload - Drag and Drop or Selected File Display */}
                    {!selectedFile ? (
                        <div
                            className={`flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center transition-all ${
                                isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/30"
                            }`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={handleUploadClick}
                        >
                            <div className="mb-3 flex items-center gap-2">
                                <Archive className={`h-8 w-8 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                                <FileText className={`h-8 w-8 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                            </div>
                            <p className={`mb-1 text-sm font-medium transition-colors ${isDragging ? "text-primary" : "text-foreground"}`}>{isDragging ? "Drop skill file here" : "Drag and drop skill file here"}</p>
                            <p className="text-muted-foreground text-xs">Supports .zip (skill package), .SKILL.md, and .json files</p>
                            <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".zip,.md,.json" disabled={isImporting} className="hidden" />
                        </div>
                    ) : (
                        <div className="bg-muted/30 flex items-center gap-3 rounded-md border p-4">
                            {previewData?.isZip ? <Archive className="text-primary h-5 w-5 flex-shrink-0" /> : <FileText className="text-primary h-5 w-5 flex-shrink-0" />}
                            <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium">{selectedFile.name}</p>
                                {previewData?.isZip && <p className="text-muted-foreground text-xs">Skill package (ZIP)</p>}
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setSelectedFile(null);
                                    setPreviewData(null);
                                    setError(null);
                                }}
                                disabled={isImporting}
                            >
                                Change
                            </Button>
                        </div>
                    )}

                    {/* Error Display */}
                    {error && <MessageBanner variant="error" message={error} />}

                    {/* Preview */}
                    {previewData && !error && (
                        <div className="space-y-4">
                            <Alert>
                                <CheckCircle className="h-4 w-4" />
                                <AlertDescription>{previewData.isZip ? "ZIP file selected. Contents will be validated on import." : "File validated successfully. Review the details below:"}</AlertDescription>
                            </Alert>

                            <div className="space-y-3 rounded-lg border p-4">
                                <div>
                                    <Label className="text-muted-foreground text-xs">Name</Label>
                                    <p className="font-medium">{previewData.name}</p>
                                </div>

                                <div>
                                    <Label className="text-muted-foreground text-xs">Description</Label>
                                    <p className="text-sm">{previewData.description}</p>
                                </div>

                                {previewData.summary && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Summary</Label>
                                        <p className="text-sm">{previewData.summary}</p>
                                    </div>
                                )}

                                {previewData.involvedAgents && previewData.involvedAgents.length > 0 && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Involved Agents</Label>
                                        <p className="text-sm">{previewData.involvedAgents.join(", ")}</p>
                                    </div>
                                )}

                                {previewData.isZip && (
                                    <div className="bg-muted/50 space-y-2 rounded-md p-3">
                                        <div className="flex items-center gap-2 text-sm font-medium">
                                            <FolderTree className="text-muted-foreground h-4 w-4" />
                                            <span>Supported Skill Package Structure</span>
                                        </div>
                                        <div className="text-muted-foreground space-y-0.5 pl-6 font-mono text-xs">
                                            <div>skill-name/</div>
                                            <div className="pl-4">
                                                ├── SKILL.md <span className="text-primary">(required)</span>
                                            </div>
                                            <div className="pl-4">
                                                ├── scripts/ <span className="opacity-60">(optional)</span>
                                            </div>
                                            <div className="pl-8">└── *.py, *.sh</div>
                                            <div className="pl-4">
                                                └── resources/ <span className="opacity-60">(optional)</span>
                                            </div>
                                            <div className="pl-8">└── data files, templates</div>
                                        </div>
                                        <p className="text-muted-foreground mt-2 text-xs">SKILL.md contains YAML frontmatter (name, description) and markdown instructions.</p>
                                    </div>
                                )}
                            </div>

                            {/* Import Options */}
                            <div className="space-y-3 rounded-lg border p-4">
                                <Label className="text-sm font-medium">Import Options</Label>

                                <div className="space-y-2">
                                    <Label htmlFor="import-scope" className="text-sm">
                                        Scope
                                    </Label>
                                    <Select value={scope} onValueChange={setScope}>
                                        <SelectTrigger id="import-scope">
                                            <SelectValue placeholder="Select scope" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="user">User (Private)</SelectItem>
                                            <SelectItem value="shared">Shared</SelectItem>
                                            <SelectItem value="global">Global</SelectItem>
                                            <SelectItem value="agent">Agent-specific</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <p className="text-muted-foreground text-xs">Choose who can access this skill after import.</p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleClose} disabled={isImporting}>
                        Cancel
                    </Button>
                    <Button onClick={handleImport} disabled={isImporting || !selectedFile}>
                        {isImporting ? "Importing..." : "Import"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
