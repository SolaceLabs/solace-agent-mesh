import React, { useState, useRef } from "react";
import { FileJson, Upload as UploadIcon, AlertCircle } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    Button,
    Input,
    Label,
} from "@/lib/components/ui";

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

export const ProjectImportDialog: React.FC<ProjectImportDialogProps> = ({
    open,
    onOpenChange,
    onImport,
}) => {
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
        if (!file.name.endsWith('.zip')) {
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
            const JSZip = (await import('jszip')).default;
            const zip = await JSZip.loadAsync(file);
            
            // Check for project.json
            if (!zip.files['project.json']) {
                setError("Invalid project export: missing project.json");
                return false;
            }

            // Parse project.json
            const projectJsonContent = await zip.files['project.json'].async('string');
            const projectData = JSON.parse(projectJsonContent);

            // Validate version
            if (projectData.version !== '1.0') {
                setError(`Unsupported export version: ${projectData.version}`);
                return false;
            }

            // Count artifacts in the ZIP
            const artifactFiles = Object.keys(zip.files).filter(
                name => name.startsWith('artifacts/') && name !== 'artifacts/'
            );

            // Extract artifact filenames (remove 'artifacts/' prefix)
            const artifactNames = artifactFiles.map(path => path.replace('artifacts/', ''));

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
                    <DialogDescription>
                        Import a project from a ZIP export file
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* File Upload */}
                    <div className="space-y-2">
                        <Label>Project File</Label>
                        
                        {!selectedFile ? (
                            <div
                                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                                    isDragging
                                        ? "border-primary bg-primary/5 scale-105"
                                        : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50"
                                }`}
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <UploadIcon className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                                <p className="text-sm font-medium mb-1">
                                    Drag and drop ZIP file here
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    or click to browse
                                </p>
                            </div>
                        ) : (
                            <div className="flex items-center gap-3 p-3 border rounded-lg bg-muted/50">
                                <FileJson className="h-5 w-5 text-primary flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium break-words line-clamp-2" title={selectedFileName}>
                                        {selectedFileName}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                    </p>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleChangeFile}
                                    disabled={isImporting}
                                    className="flex-shrink-0"
                                >
                                    Change
                                </Button>
                            </div>
                        )}

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".zip"
                            onChange={handleFileInputChange}
                            className="hidden"
                        />
                    </div>

                    {/* Project Preview */}
                    {projectPreview && (
                        <div className="space-y-3 p-4 border rounded-lg bg-muted/30">
                            <div>
                                <Label className="text-xs text-muted-foreground">Original Name</Label>
                                <p className="text-sm font-medium">{projectPreview.name}</p>
                            </div>
                            {projectPreview.description && (
                                <div>
                                    <Label className="text-xs text-muted-foreground">Description</Label>
                                    <p className="text-sm">{projectPreview.description}</p>
                                </div>
                            )}
                            {projectPreview.systemPrompt && (
                                <div>
                                    <Label className="text-xs text-muted-foreground">Instructions</Label>
                                    <p className="text-sm line-clamp-3">{projectPreview.systemPrompt}</p>
                                </div>
                            )}
                            {projectPreview.defaultAgentId && (
                                <div>
                                    <Label className="text-xs text-muted-foreground">Default Agent</Label>
                                    <p className="text-sm font-mono">{projectPreview.defaultAgentId}</p>
                                </div>
                            )}
                            <div>
                                <Label className="text-xs text-muted-foreground">
                                    Artifacts ({projectPreview.artifactCount} {projectPreview.artifactCount === 1 ? 'file' : 'files'})
                                </Label>
                                {projectPreview.artifactNames.length > 0 && (
                                    <div className="mt-1 space-y-1">
                                        {projectPreview.artifactNames.slice(0, 5).map((name, index) => (
                                            <div key={index} className="flex items-center gap-1.5 text-xs">
                                                <FileJson className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                                <span className="truncate">{name}</span>
                                            </div>
                                        ))}
                                        {projectPreview.artifactNames.length > 5 && (
                                            <p className="text-xs text-muted-foreground italic">
                                                + {projectPreview.artifactNames.length - 5} more files
                                            </p>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Custom Name Input */}
                    {projectPreview && (
                        <div className="space-y-2">
                            <Label htmlFor="customName">Project Name</Label>
                            <Input
                                id="customName"
                                value={customName}
                                onChange={(e) => setCustomName(e.target.value)}
                                placeholder="Enter project name"
                                disabled={isImporting}
                            />
                            <p className="text-xs text-muted-foreground">
                                Name conflicts will be resolved automatically
                            </p>
                        </div>
                    )}

                    {/* Error Message */}
                    {error && (
                        <div className="flex items-start gap-2 p-3 border border-destructive/50 bg-destructive/10 rounded-lg">
                            <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-destructive">{error}</p>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={handleClose}
                        disabled={isImporting}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleImport}
                        disabled={isImporting}
                    >
                        {isImporting ? "Importing..." : "Import"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};