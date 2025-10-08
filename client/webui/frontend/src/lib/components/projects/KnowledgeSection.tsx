import React, { useRef, useState } from "react";
import { Upload, FileText, ChevronDown, ChevronRight } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
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
    const { onDownload } = useDownload();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [isCollapsed, setIsCollapsed] = useState(false);
    const [filesToUpload, setFilesToUpload] = useState<FileList | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

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
            <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-accent/50"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <div className="flex items-center gap-2">
                    {isCollapsed ? (
                        <ChevronRight className="h-4 w-4" />
                    ) : (
                        <ChevronDown className="h-4 w-4" />
                    )}
                    <h3 className="text-sm font-semibold text-foreground">Knowledge</h3>
                    {!isLoading && artifacts.length > 0 && (
                        <span className="text-xs text-muted-foreground">({artifacts.length})</span>
                    )}
                </div>
                {!isCollapsed && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                            e.stopPropagation();
                            handleUploadClick();
                        }}
                    >
                        <Upload className="h-4 w-4 mr-2" />
                        Upload
                    </Button>
                )}
            </div>

            {!isCollapsed && (
                <div className="px-4 pb-3">
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
                        <div className="flex flex-col items-center justify-center p-6 text-center border border-dashed rounded-md">
                            <FileText className="h-8 w-8 text-muted-foreground mb-2" />
                            <p className="text-sm text-muted-foreground">
                                No files uploaded yet
                            </p>
                        </div>
                    )}

                    {!isLoading && !error && artifacts.length > 0 && (
                        <div className="space-y-1 max-h-[400px] overflow-y-auto">
                            {artifacts.map((artifact) => (
                                <DocumentListItem
                                    key={artifact.filename}
                                    artifact={artifact}
                                    onDownload={() => onDownload(artifact)}
                                    onDelete={() => handleDelete(artifact.filename)}
                                />
                            ))}
                        </div>
                    )}

                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        className="hidden"
                        multiple
                    />
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
