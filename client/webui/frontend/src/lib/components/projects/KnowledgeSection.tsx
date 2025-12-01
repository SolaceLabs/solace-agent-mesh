import React, { useRef, useState } from "react";
import { Upload } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Spinner } from "@/lib/components/ui/spinner";
import { useDownload } from "@/lib/hooks/useDownload";
import type { Project } from "@/lib/types/projects";
import { DocumentListItem } from "./DocumentListItem";
import { AddProjectFilesDialog } from "./AddProjectFilesDialog";
import { useAddFilesToProject, useProjectArtifacts } from "@/features/projects/api/hooks";

interface KnowledgeSectionProps {
    project: Project;
}

export const KnowledgeSection: React.FC<KnowledgeSectionProps> = ({ project }) => {
    const { data: artifacts, isLoading, error, isSuccess } = useProjectArtifacts(project.id);
    const { onDownload } = useDownload(project.id);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [filesToUpload, setFilesToUpload] = useState<FileList | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDragging, setIsDragging] = useState(false);

    const addFilesToProject = useAddFilesToProject(project.id);

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

    const handleConfirmUpload = (files: File[], fileMetadata: Record<string, string>) => {
        setIsSubmitting(true);
        addFilesToProject.mutate(
            { files, fileMetadata },
            {
                onSuccess: async () => {
                    setFilesToUpload(null);
                    setIsSubmitting(false);
                },
            }
        );
    };

    return (
        <div className="mb-6">
            <div className="mb-3 flex items-center justify-between px-4">
                <div className="flex items-center gap-2">
                    <h3 className="text-foreground text-sm font-semibold">Knowledge</h3>
                    {isSuccess && artifacts.length > 0 && <span className="text-muted-foreground text-xs">({artifacts.length})</span>}
                </div>
                <Button variant="ghost" size="sm" onClick={handleUploadClick}>
                    <Upload className="mr-2 h-4 w-4" />
                    Upload
                </Button>
            </div>

            <div className="px-4 pb-3" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
                {isLoading && (
                    <div className="flex items-center justify-center p-4">
                        <Spinner size="small" />
                    </div>
                )}

                {error && <div className="text-destructive border-destructive/50 rounded-md border p-3 text-sm">Error loading files: {error.message}</div>}

                {isSuccess && artifacts.length === 0 && (
                    <div className={`flex flex-col items-center justify-center rounded-md border-2 border-dashed p-6 text-center transition-all ${isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/30"}`}>
                        <Upload className={`mb-3 h-10 w-10 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                        <p className={`mb-1 text-sm font-medium transition-colors ${isDragging ? "text-primary" : "text-foreground"}`}>{isDragging ? "Drop files here to upload" : "Drag and drop files here"}</p>
                        <p className="text-muted-foreground text-xs">or click the Upload button above</p>
                    </div>
                )}

                {isSuccess && artifacts.length > 0 && (
                    <>
                        <div className={`mb-2 rounded-md border-2 border-dashed p-3 text-center transition-all ${isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/20 bg-muted/30"}`}>
                            <Upload className={`mx-auto mb-1 h-5 w-5 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                            <p className={`text-xs transition-colors ${isDragging ? "text-primary font-medium" : "text-muted-foreground"}`}>{isDragging ? "Drop files here to upload" : "Drag and drop files here to upload"}</p>
                        </div>
                        <div className="max-h-[400px] space-y-1 overflow-y-auto rounded-md">
                            {artifacts.map(artifact => (
                                <DocumentListItem key={artifact.filename} project={project} artifact={artifact} onDownload={() => onDownload(artifact)} />
                            ))}
                        </div>
                    </>
                )}

                <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" multiple />
            </div>

            <AddProjectFilesDialog isOpen={!!filesToUpload} files={filesToUpload} onClose={() => setFilesToUpload(null)} onConfirm={handleConfirmUpload} isSubmitting={isSubmitting} />
        </div>
    );
};
