import React, { useState, useRef } from "react";
import { FileJson, Upload as UploadIcon, AlertCircle } from "lucide-react";
import JSZip from "jszip";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, Button, Input, Label } from "@/lib/components/ui";

interface ProjectImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (file: File, options: { preserveName: boolean; customName?: string }) => Promise<void>;
}

interface ProjectPreview {
    name: string;
    description?: string;
    systemPrompt?: string;
    defaultAgentId?: string;
    artifactCount: number;
    artifactNames: string[];
}

export const ProjectImportDialog: React.FC<ProjectImportDialogProps> = ({ open, onOpenChange, onImport }) => {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [selectedFileName, setSelectedFileName] = useState<string>("");
    const [projectPreview, setProjectPreview] = useState<ProjectPreview | null>(null);
    const [customName, setCustomName] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isImporting, setIsImporting] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleClose = () => {
        if (!isImporting) {
            setSelectedFile(null);
            setSelectedFileName("");
            setProjectPreview(null);
            setCustomName("");
            setError(null);
            onOpenChange(false);
        }
    };

    const validateAndPreviewFile = async (file: File) => {
        setError(null);

        // Validate file type
        if (!file.name.endsWith(".zip")) {
            setError("Please select a ZIP file");
            return false;
        }

        // Validate file size (max 100MB)
        const maxSize = 100 * 1024 * 1024;
        if (file.size > maxSize) {
            setError("File size exceeds 100MB limit");
            return false;
        }

        try {
            // Use JSZip to read and parse the ZIP file
            const zip = await JSZip.loadAsync(file);

            // Check for project.json
            if (!zip.files["project.json"]) {
                setError("Invalid project export: missing project.json");
                return false;
            }

            // Parse project.json
            const projectJsonContent = await zip.files["project.json"].async("string");
            const projectData = JSON.parse(projectJsonContent);

            // Validate version
            if (projectData.version !== "1.0") {
                setError(`Unsupported export version: ${projectData.version}`);
                return false;
            }

            // Count artifacts in the ZIP
            const artifactFiles = Object.keys(zip.files).filter(name => name.startsWith("artifacts/") && name !== "artifacts/");

            // Extract artifact filenames (remove 'artifacts/' prefix)
            const artifactNames = artifactFiles.map(path => path.replace("artifacts/", ""));

            // Set preview with all metadata
            setProjectPreview({
                name: projectData.project.name,
                description: projectData.project.description,
                systemPrompt: projectData.project.systemPrompt,
                defaultAgentId: projectData.project.defaultAgentId,
                artifactCount: artifactFiles.length,
                artifactNames: artifactNames,
            });

            // Set default custom name
            setCustomName(projectData.project.name);

            return true;
        } catch (err) {
            console.error("Error validating file:", err);
            setError("Invalid ZIP file or corrupted project export");
            return false;
        }
    };

    const handleFileSelect = async (file: File) => {
        setSelectedFile(file);
        setSelectedFileName(file.name);
        await validateAndPreviewFile(file);
    };

    const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            await handleFileSelect(file);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const file = e.dataTransfer.files[0];
        if (file) {
            await handleFileSelect(file);
        }
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
                preserveName: false,
                customName: customName.trim() || undefined,
            });
            handleClose();
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Failed to import project";
            setError(errorMessage);
        } finally {
            setIsImporting(false);
        }
    };

    const handleChangeFile = () => {
        setSelectedFile(null);
        setSelectedFileName("");
        setProjectPreview(null);
        setCustomName("");
        setError(null);
        fileInputRef.current?.click();
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Import Project</DialogTitle>
                    <DialogDescription>Import a project from a ZIP export file</DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* File Upload */}
                    <div className="space-y-2">
                        <Label>Project File</Label>

                        {!selectedFile ? (
                            <div
                                className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
                                    isDragging ? "border-primary bg-primary/5 scale-105" : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50"
                                }`}
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <UploadIcon className="text-muted-foreground mx-auto mb-4 h-12 w-12" />
                                <p className="mb-1 text-sm font-medium">Drag and drop ZIP file here</p>
                                <p className="text-muted-foreground text-xs">or click to browse</p>
                            </div>
                        ) : (
                            <div className="bg-muted/50 flex items-center gap-3 rounded-lg border p-3">
                                <FileJson className="text-primary h-5 w-5 flex-shrink-0" />
                                <div className="min-w-0 flex-1">
                                    <p className="line-clamp-2 text-sm font-medium break-words" title={selectedFileName}>
                                        {selectedFileName}
                                    </p>
                                    <p className="text-muted-foreground text-xs">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                                </div>
                                <Button variant="ghost" size="sm" onClick={handleChangeFile} disabled={isImporting} className="flex-shrink-0">
                                    Change
                                </Button>
                            </div>
                        )}

                        <input ref={fileInputRef} type="file" accept=".zip" onChange={handleFileInputChange} className="hidden" />
                    </div>

                    {/* Project Preview */}
                    {projectPreview && (
                        <div className="bg-muted/30 space-y-3 rounded-lg border p-4">
                            <div>
                                <Label className="text-muted-foreground text-xs">Original Name</Label>
                                <p className="text-sm font-medium">{projectPreview.name}</p>
                            </div>
                            {projectPreview.description && (
                                <div>
                                    <Label className="text-muted-foreground text-xs">Description</Label>
                                    <p className="text-sm">{projectPreview.description}</p>
                                </div>
                            )}
                            {projectPreview.systemPrompt && (
                                <div>
                                    <Label className="text-muted-foreground text-xs">Instructions</Label>
                                    <p className="line-clamp-3 text-sm">{projectPreview.systemPrompt}</p>
                                </div>
                            )}
                            {projectPreview.defaultAgentId && (
                                <div>
                                    <Label className="text-muted-foreground text-xs">Default Agent</Label>
                                    <p className="font-mono text-sm">{projectPreview.defaultAgentId}</p>
                                </div>
                            )}
                            <div>
                                <Label className="text-muted-foreground text-xs">
                                    Artifacts ({projectPreview.artifactCount} {projectPreview.artifactCount === 1 ? "file" : "files"})
                                </Label>
                                {projectPreview.artifactNames.length > 0 && (
                                    <div className="mt-1 space-y-1">
                                        {projectPreview.artifactNames.slice(0, 5).map((name, index) => (
                                            <div key={index} className="flex items-center gap-1.5 text-xs">
                                                <FileJson className="text-muted-foreground h-3 w-3 flex-shrink-0" />
                                                <span className="truncate">{name}</span>
                                            </div>
                                        ))}
                                        {projectPreview.artifactNames.length > 5 && <p className="text-muted-foreground text-xs italic">+ {projectPreview.artifactNames.length - 5} more files</p>}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Custom Name Input */}
                    {projectPreview && (
                        <div className="space-y-2">
                            <Label htmlFor="customName">Project Name</Label>
                            <Input id="customName" value={customName} onChange={e => setCustomName(e.target.value)} placeholder="Enter project name" disabled={isImporting} />
                            <p className="text-muted-foreground text-xs">Name conflicts will be resolved automatically</p>
                        </div>
                    )}

                    {/* Error Message */}
                    {error && (
                        <div className="border-destructive/50 bg-destructive/10 flex items-start gap-2 rounded-lg border p-3">
                            <AlertCircle className="text-destructive mt-0.5 h-4 w-4 flex-shrink-0" />
                            <p className="text-destructive text-sm">{error}</p>
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
