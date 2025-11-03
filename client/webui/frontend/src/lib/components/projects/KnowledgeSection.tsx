import React, { useRef, useState } from "react";
import { Upload } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Spinner } from "@/lib/components/ui/spinner";
import { useProjectArtifacts } from "@/lib/hooks/useProjectArtifacts";
import { useProjectContext } from "@/lib/providers";
import { useDownload } from "@/lib/hooks/useDownload";
import type { Project } from "@/lib/types/projects";
import { DocumentListItem } from "./DocumentListItem";
import { AddProjectFilesDialog } from "./AddProjectFilesDialog";

interface KnowledgeSectionProps {
    project: Project;
}

export const KnowledgeSection: React.FC<KnowledgeSectionProps> = ({ project }) => {
    const { artifacts, isLoading, error, refetch } = useProjectArtifacts(project.id);
    const { addFilesToProject, removeFileFromProject } = useProjectContext();
    const { onDownload } = useDownload(project.id);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [filesToUpload, setFilesToUpload] = useState<FileList | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDragging, setIsDragging] = useState(false);

    const sortedArtifacts = React.useMemo(() => {
        return [...artifacts].sort((a, b) => {
            const dateA = a.last_modified ? new Date(a.last_modified).getTime() : 0;
            const dateB = b.last_modified ? new Date(b.last_modified).getTime() : 0;
            return dateB - dateA; 
        });
    }, [artifacts]);

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files && files.length > 0) {
            const dataTransfer = new DataTransfer();
            Array.from(files).forEach(file => dataTransfer.items.add(file));
            setFilesToUpload(dataTransfer.files);
        }
        if (event.target) {
            event.target.value = "";
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
            const dataTransfer = new DataTransfer();
            Array.from(files).forEach(file => dataTransfer.items.add(file));
            setFilesToUpload(dataTransfer.files);
        }
    };

    const handleConfirmUpload = async (formData: FormData) => {
        setIsSubmitting(true);
        try {
            await addFilesToProject(project.id, formData);
            await refetch();
            setFilesToUpload(null);
        } catch (e) {
            console.error("Failed to add files:", e);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async (filename: string) => {
        if (window.confirm(`Are you sure you want to delete ${filename}?`)) {
            try {
                await removeFileFromProject(project.id, filename);
                await refetch();
            } catch (e) {
                console.error(`Failed to delete file ${filename}:`, e);
            }
        }
    };

    return (
        <div className="border-b">
            <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-foreground">Knowledge</h3>
                    {!isLoading && artifacts.length > 0 && (
                        <span className="text-xs text-muted-foreground">({artifacts.length})</span>
                    )}
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleUploadClick}
                >
                    <Upload className="h-4 w-4 mr-2" />
                    Upload
                </Button>
            </div>

            <div
                className="px-4 pb-3"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
            >
                {isLoading && (
                    <div className="flex items-center justify-center p-4">
                        <Spinner size="small" />
                    </div>
                )}

                {error && (
                    <div className="text-sm text-destructive p-3 border border-destructive/50 rounded-md">
                        Error loading files: {error}
                    </div>
                )}

                {!isLoading && !error && artifacts.length === 0 && (
                    <div className={`flex flex-col items-center justify-center p-6 text-center border-2 border-dashed rounded-md transition-all ${
                        isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/30"
                    }`}>
                        <Upload className={`h-10 w-10 mb-3 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                        <p className={`text-sm font-medium mb-1 transition-colors ${isDragging ? "text-primary" : "text-foreground"}`}>
                            {isDragging ? "Drop files here to upload" : "Drag and drop files here"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                            or click the Upload button above
                        </p>
                    </div>
                )}

                {!isLoading && !error && artifacts.length > 0 && (
                    <>
                        <div className={`mb-2 p-3 border-2 border-dashed rounded-md text-center transition-all ${
                            isDragging
                                ? "border-primary bg-primary/10 scale-[1.02]"
                                : "border-muted-foreground/20 bg-muted/30"
                        }`}>
                            <Upload className={`h-5 w-5 mx-auto mb-1 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                            <p className={`text-xs transition-colors ${isDragging ? "text-primary font-medium" : "text-muted-foreground"}`}>
                                {isDragging ? "Drop files here to upload" : "Drag and drop files here to upload"}
                            </p>
                        </div>
                        <div className="space-y-1 max-h-[400px] overflow-y-auto rounded-md">
                            {sortedArtifacts.map((artifact) => (
                                <DocumentListItem
                                    key={artifact.filename}
                                    artifact={artifact}
                                    onDownload={() => onDownload(artifact)}
                                    onDelete={() => handleDelete(artifact.filename)}
                                />
                            ))}
                        </div>
                    </>
                )}

                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    multiple
                />
            </div>

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
