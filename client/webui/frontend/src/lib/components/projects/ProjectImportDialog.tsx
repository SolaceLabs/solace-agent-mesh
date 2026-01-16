import React, { useState } from "react";
import { FileJson, AlertTriangle } from "lucide-react";
import JSZip from "jszip";

import { Input, Label } from "@/lib/components/ui";
import { MessageBanner, FileUpload, ConfirmationDialog } from "@/lib/components/common";
import { useConfigContext } from "@/lib/hooks";
import { formatBytes } from "@/lib/utils";

interface ProjectImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (file: File, options: { preserveName: boolean; customName?: string }) => Promise<void>;
}

interface ArtifactPreviewInfo {
    name: string;
    size: number;
    isOversized: boolean;
}

interface ProjectPreview {
    name: string;
    description?: string;
    systemPrompt?: string;
    defaultAgentId?: string;
    artifactCount: number;
    artifactNames: string[];
    artifacts: ArtifactPreviewInfo[];
    oversizedArtifacts: ArtifactPreviewInfo[];
}

// Default max ZIP upload size (100MB) - fallback if not configured
const DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024;

export const ProjectImportDialog: React.FC<ProjectImportDialogProps> = ({ open, onOpenChange, onImport }) => {
    const { validationLimits } = useConfigContext();
    const maxUploadSizeBytes = validationLimits?.maxUploadSizeBytes;
    const maxZipUploadSizeBytes = validationLimits?.maxZipUploadSizeBytes ?? DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES;

    const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
    const [projectPreview, setProjectPreview] = useState<ProjectPreview | null>(null);
    const [customName, setCustomName] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isImporting, setIsImporting] = useState(false);

    const selectedFile = selectedFiles?.[0] || null;

    const handleClose = () => {
        if (!isImporting) {
            setSelectedFiles(null);
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

        // Validate ZIP file size against configurable limit
        if (file.size > maxZipUploadSizeBytes) {
            setError(`ZIP file size exceeds ${formatBytes(maxZipUploadSizeBytes)} limit`);
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
            // Currently only version 1.0 is supported. Future versions may require migration logic.
            // TODO: Consider implementing version migration strategies if format changes are needed
            if (projectData.version !== "1.0") {
                setError(`Unsupported export version: ${projectData.version}. Only version 1.0 is currently supported.`);
                return false;
            }

            // Count artifacts in the ZIP and check their sizes
            const artifactFiles = Object.keys(zip.files).filter(name => name.startsWith("artifacts/") && name !== "artifacts/");

            // Extract artifact filenames and sizes (remove 'artifacts/' prefix)
            const artifactNames = artifactFiles.map(path => path.replace("artifacts/", ""));

            // Build a map of artifact sizes from project.json metadata if available
            const artifactMetadata = projectData.artifacts || [];
            const sizeMap = new Map<string, number>();
            for (const meta of artifactMetadata) {
                if (meta.filename && typeof meta.size === "number") {
                    sizeMap.set(meta.filename, meta.size);
                }
            }

            // Get artifact sizes and check for oversized files
            const artifacts: ArtifactPreviewInfo[] = [];
            const oversizedArtifacts: ArtifactPreviewInfo[] = [];

            for (const artifactPath of artifactFiles) {
                const zipEntry = zip.files[artifactPath];
                const filename = artifactPath.replace("artifacts/", "");

                // Get size from metadata map, or read the file content to determine size
                let size = sizeMap.get(filename);
                if (size === undefined) {
                    // Fallback: read the file content to get its size
                    // This is slower but works when metadata is not available
                    try {
                        const content = await zipEntry.async("uint8array");
                        size = content.length;
                    } catch {
                        size = 0;
                    }
                }

                const isOversized = maxUploadSizeBytes ? size > maxUploadSizeBytes : false;

                const artifactInfo: ArtifactPreviewInfo = { name: filename, size, isOversized };
                artifacts.push(artifactInfo);

                if (isOversized) {
                    oversizedArtifacts.push(artifactInfo);
                }
            }

            // Set preview with all metadata
            setProjectPreview({
                name: projectData.project.name,
                description: projectData.project.description,
                systemPrompt: projectData.project.systemPrompt,
                defaultAgentId: projectData.project.defaultAgentId,
                artifactCount: artifactFiles.length,
                artifactNames: artifactNames,
                artifacts,
                oversizedArtifacts,
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

    const handleFileChange = async (files: FileList | null) => {
        setSelectedFiles(files);
        if (files && files[0]) {
            await validateAndPreviewFile(files[0]);
        } else {
            setProjectPreview(null);
            setCustomName("");
        }
    };

    const handleFileValidation = (files: FileList): { valid: boolean; error?: string } => {
        const file = files[0];

        // Validate file type
        if (!file.name.endsWith(".zip")) {
            return { valid: false, error: "Please select a ZIP file" };
        }

        // Validate ZIP file size against configurable limit
        if (file.size > maxZipUploadSizeBytes) {
            return { valid: false, error: `ZIP file size exceeds ${formatBytes(maxZipUploadSizeBytes)} limit` };
        }

        return { valid: true };
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
            // Reset state on success - ConfirmationDialog will handle closing
            setSelectedFiles(null);
            setProjectPreview(null);
            setCustomName("");
            setError(null);
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Failed to import project";
            setError(errorMessage);
            throw err; // Re-throw to prevent dialog from closing on import errors
        } finally {
            setIsImporting(false);
        }
    };

    const handleCancel = () => {
        if (!isImporting) {
            handleClose();
        }
    };

    const dialogContent = (
        <div className="space-y-4">
            {/* File Upload */}
            <div className="mt-2 py-2">
                <FileUpload name="projectFile" accept=".zip" multiple={false} disabled={isImporting} value={selectedFiles} onChange={handleFileChange} onValidate={handleFileValidation} testid="projectImportFileInput" />
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
                        {projectPreview.artifacts.length > 0 && (
                            <div className="mt-1 space-y-1">
                                {projectPreview.artifacts.slice(0, 5).map((artifact, index) => (
                                    <div key={index} className={`flex items-center gap-1.5 text-xs ${artifact.isOversized ? "text-destructive" : ""}`}>
                                        {artifact.isOversized ? <AlertTriangle className="text-destructive h-3 w-3 flex-shrink-0" /> : <FileJson className="text-muted-foreground h-3 w-3 flex-shrink-0" />}
                                        <span className="truncate">{artifact.name}</span>
                                        <span className="text-muted-foreground flex-shrink-0">({formatBytes(artifact.size)})</span>
                                    </div>
                                ))}
                                {projectPreview.artifacts.length > 5 && <p className="text-muted-foreground text-xs italic">+ {projectPreview.artifacts.length - 5} more files</p>}
                            </div>
                        )}
                    </div>

                    {/* Warning for oversized artifacts */}
                    {projectPreview.oversizedArtifacts.length > 0 && maxUploadSizeBytes && (
                        <div className="mt-2">
                            <MessageBanner
                                variant="warning"
                                message={`${projectPreview.oversizedArtifacts.length} ${projectPreview.oversizedArtifacts.length === 1 ? "file exceeds" : "files exceed"} the maximum size of ${formatBytes(maxUploadSizeBytes)} and will be skipped during import: ${projectPreview.oversizedArtifacts
                                    .slice(0, 3)
                                    .map(a => a.name)
                                    .join(", ")}${projectPreview.oversizedArtifacts.length > 3 ? ` and ${projectPreview.oversizedArtifacts.length - 3} more` : ""}`}
                            />
                        </div>
                    )}
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
            {error && <MessageBanner variant="error" message={error} />}
        </div>
    );

    return (
        <ConfirmationDialog
            open={open}
            onOpenChange={open => !open && handleClose()}
            title="Import Project"
            description="Import a project from an exported project ZIP file."
            content={dialogContent}
            actionLabels={{ confirm: "Import", cancel: "Cancel" }}
            onConfirm={handleImport}
            onCancel={handleCancel}
            isLoading={isImporting}
            isEnabled={!!projectPreview}
        />
    );
};
