import React, { useRef, useState } from "react";
import { Loader2, FileText, AlertTriangle, Plus } from "lucide-react";

import { useProjectArtifacts } from "@/lib/hooks/useProjectArtifacts";
import type { Project } from "@/lib/types/projects";
import { Button } from "@/lib/components/ui";
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
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [filesToUpload, setFilesToUpload] = useState<FileList | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleAddFilesClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files && files.length > 0) {
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
        try {
            await addFilesToProject(project.id, formData);
            await refetch();
            setFilesToUpload(null); // Close dialog on success
        } catch (e) {
            // Error is handled in the provider, but we could add a local notification here if needed.
            console.error("Failed to add files:", e);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-6">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                <AlertTriangle className="h-4 w-4" />
                <span>Error loading files: {error}</span>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <h4 className="font-semibold text-foreground">Project Files</h4>
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
                <div className="flex flex-col items-center justify-center rounded-md border border-dashed p-8 text-center text-muted-foreground">
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
            <AddProjectFilesDialog
                isOpen={!!filesToUpload}
                files={filesToUpload}
                onClose={() => setFilesToUpload(null)}
                onConfirm={handleConfirmUpload}
                isSubmitting={isSubmitting}
            />
        </div>
    );
};
