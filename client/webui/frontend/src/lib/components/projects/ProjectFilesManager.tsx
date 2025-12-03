import React, { useRef, useState, useCallback } from "react";
import { Loader2, FileText, AlertTriangle, Plus } from "lucide-react";

import { useProjectArtifacts } from "@/lib/hooks/useProjectArtifacts";
import { useConfigContext } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { Button } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { useProjectContext } from "@/lib/providers";
import { ArtifactCard } from "../chat/artifact/ArtifactCard";
import { AddProjectFilesDialog } from "./AddProjectFilesDialog";

interface ProjectFilesManagerProps {
    project: Project;
    isEditing: boolean;
}

export const ProjectFilesManager: React.FC<ProjectFilesManagerProps> = ({ project, isEditing }) => {
    const { artifacts, isLoading, error, refetch } = useProjectArtifacts(project.id);
    const { addFilesToProject } = useProjectContext();
    const { validationLimits } = useConfigContext();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const maxUploadSizeBytes = validationLimits?.maxUploadSizeBytes;

    const [filesToUpload, setFilesToUpload] = useState<FileList | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [fileSizeError, setFileSizeError] = useState<string | null>(null);

    // Validate file sizes before showing upload dialog
    // If maxUploadSizeBytes is not configured, skip client-side validation and let backend handle it
    const validateFileSizes = useCallback(
        (files: FileList): { valid: boolean; error?: string } => {
            // Skip validation if max size is not configured
            if (!maxUploadSizeBytes) {
                return { valid: true };
            }

            const oversizedFiles: string[] = [];
            const maxSizeMB = maxUploadSizeBytes / (1024 * 1024);

            for (const file of Array.from(files)) {
                if (file.size > maxUploadSizeBytes) {
                    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
                    oversizedFiles.push(`${file.name} (${fileSizeMB} MB)`);
                }
            }

            if (oversizedFiles.length > 0) {
                const errorMsg =
                    oversizedFiles.length === 1
                        ? `File "${oversizedFiles[0]}" exceeds the maximum size of ${maxSizeMB.toFixed(0)} MB.`
                        : `${oversizedFiles.length} files exceed the maximum size of ${maxSizeMB.toFixed(0)} MB:\n${oversizedFiles.slice(0, 3).join(", ")}${oversizedFiles.length > 3 ? ` and ${oversizedFiles.length - 3} more` : ""}`;
                return { valid: false, error: errorMsg };
            }

            return { valid: true };
        },
        [maxUploadSizeBytes]
    );

    const handleAddFilesClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files && files.length > 0) {
            // Validate file sizes first
            const validation = validateFileSizes(files);
            if (!validation.valid) {
                setFileSizeError(validation.error || "One or more files exceed the maximum allowed size.");
                if (event.target) {
                    event.target.value = "";
                }
                return;
            }

            setFileSizeError(null);
            // Create a new FileList from the selected files to avoid issues with
            // the input being cleared while the state update is pending.
            const dataTransfer = new DataTransfer();
            Array.from(files).forEach(file => dataTransfer.items.add(file));
            setFilesToUpload(dataTransfer.files);
        }

        // Reset file input to allow selecting the same file again
        if (event.target) {
            event.target.value = "";
        }
    };

    const handleConfirmUpload = async (formData: FormData) => {
        setIsSubmitting(true);
        setUploadError(null);
        try {
            await addFilesToProject(project.id, formData);
            await refetch();
            setFilesToUpload(null); // Close dialog on success
        } catch (e) {
            console.error("Failed to add files:", e);
            const errorMessage = e instanceof Error ? e.message : "Failed to upload files. Please try again.";
            setUploadError(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleCloseUploadDialog = () => {
        setFilesToUpload(null);
        setUploadError(null);
    };

    const handleClearUploadError = () => {
        setUploadError(null);
    };

    const handleClearFileSizeError = () => {
        setFileSizeError(null);
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-6">
                <Loader2 className="text-muted-foreground size-6 animate-spin" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="border-destructive/50 bg-destructive/10 text-destructive flex items-center gap-2 rounded-md border p-4 text-sm">
                <AlertTriangle className="h-4 w-4" />
                <span>Error loading files: {error}</span>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {/* File size validation error banner */}
            {fileSizeError && <MessageBanner variant="error" message={fileSizeError} dismissible onDismiss={handleClearFileSizeError} />}

            <div className="flex items-center justify-between">
                <h4 className="text-foreground font-semibold">Project Files</h4>
                {isEditing && (
                    <>
                        <Button onClick={handleAddFilesClick} variant="outline" size="sm" className="flex items-center gap-1">
                            <Plus className="h-4 w-4" />
                            Add File(s)
                        </Button>
                        <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" multiple />
                    </>
                )}
            </div>
            {artifacts.length === 0 ? (
                <div className="text-muted-foreground flex flex-col items-center justify-center rounded-md border border-dashed p-8 text-center">
                    <FileText className="mb-2 h-8 w-8" />
                    <p>No files have been added to this project yet.</p>
                </div>
            ) : (
                <div className="overflow-hidden rounded-md border">
                    {artifacts.map(artifact => (
                        <ArtifactCard key={artifact.filename} artifact={artifact} />
                    ))}
                </div>
            )}
            <AddProjectFilesDialog isOpen={!!filesToUpload} files={filesToUpload} onClose={handleCloseUploadDialog} onConfirm={handleConfirmUpload} isSubmitting={isSubmitting} error={uploadError} onClearError={handleClearUploadError} />
        </div>
    );
};
