import React, { useState, useCallback } from "react";

import { Spinner } from "@/lib/components/ui/spinner";
import { useConfigContext, useDownload, useProjectArtifacts } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import type { ArtifactInfo, Project } from "@/lib/types";
import { formatRelativeTime, validateFileSizes } from "@/lib/utils";

import { ArtifactBar } from "../chat/artifact";
import { FileDetails } from "../chat/file";
import { ConfirmationDialog, FileUpload, MessageBanner } from "../common";

import { AddProjectFilesDialog } from "./AddProjectFilesDialog";
import { EditFileDescriptionDialog } from "./EditFileDescriptionDialog";

interface KnowledgeSectionProps {
    project: Project;
}

export const KnowledgeSection: React.FC<KnowledgeSectionProps> = ({ project }) => {
    const { artifacts, isLoading, error, refetch } = useProjectArtifacts(project.id);
    const { addFilesToProject, removeFileFromProject, updateFileMetadata } = useProjectContext();
    const { onDownload } = useDownload(project.id);
    const { validationLimits } = useConfigContext();

    // Get max upload size from config - if not available, skip client-side validation
    const maxUploadSizeBytes = validationLimits?.maxUploadSizeBytes;

    const [filesToUpload, setFilesToUpload] = useState<FileList | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedArtifact, setSelectedArtifact] = useState<ArtifactInfo | null>(null);
    const [expandedArtifact, setExpandedArtifact] = useState<string | null>(null);
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [isSavingMetadata, setIsSavingMetadata] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [fileToDelete, setFileToDelete] = useState<ArtifactInfo | null>(null);

    const sortedArtifacts = React.useMemo(() => {
        return [...artifacts].sort((a, b) => {
            const dateA = a.last_modified ? new Date(a.last_modified).getTime() : 0;
            const dateB = b.last_modified ? new Date(b.last_modified).getTime() : 0;
            return dateB - dateA;
        });
    }, [artifacts]);

    // Validate file sizes before showing upload dialog
    // if maxUploadSizeBytes is not configured, validation is skipped and backend handles it
    const handleValidateFileSizes = useCallback(
        (files: FileList) => {
            return validateFileSizes(files, { maxSizeBytes: maxUploadSizeBytes });
        },
        [maxUploadSizeBytes]
    );

    const handleFileUploadChange = (files: FileList | null) => {
        setFilesToUpload(files);
    };

    const handleConfirmUpload = async (formData: FormData) => {
        setIsSubmitting(true);
        setUploadError(null);
        try {
            await addFilesToProject(project.id, formData);
            await refetch();
            setFilesToUpload(null);
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

    const handleDeleteClick = (artifact: ArtifactInfo) => {
        setFileToDelete(artifact);
    };

    const handleConfirmDelete = async () => {
        if (!fileToDelete) return;

        try {
            await removeFileFromProject(project.id, fileToDelete.filename);
            await refetch();
            setFileToDelete(null);
        } catch (e) {
            console.error(`Failed to delete file ${fileToDelete.filename}:`, e);
        }
    };

    const handleToggleExpand = (filename: string) => {
        setExpandedArtifact(expandedArtifact === filename ? null : filename);
    };

    const handleEditDescription = (artifact: ArtifactInfo) => {
        setSelectedArtifact(artifact);
        setShowEditDialog(true);
    };

    const handleSaveDescription = async (description: string) => {
        if (!selectedArtifact) return;

        setIsSavingMetadata(true);
        try {
            await updateFileMetadata(project.id, selectedArtifact.filename, description);
            await refetch();
            setShowEditDialog(false);
            setSelectedArtifact(null);
        } catch (e) {
            console.error("Failed to update file description:", e);
        } finally {
            setIsSavingMetadata(false);
        }
    };

    const handleCloseEditDialog = () => {
        setShowEditDialog(false);
        setSelectedArtifact(null);
    };

    return (
        <div className="flex min-h-0 flex-1 flex-col">
            <div className="mb-3 flex items-center justify-between px-4">
                <div className="flex items-center gap-2">
                    <h3 className="text-foreground text-sm font-semibold">Knowledge</h3>
                    {!isLoading && artifacts.length > 0 && <span className="text-muted-foreground text-xs">({artifacts.length})</span>}
                </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col px-4 pb-3">
                {isLoading && (
                    <div className="flex items-center justify-center p-4">
                        <Spinner />
                    </div>
                )}

                {error && <MessageBanner variant="error" message={`Error loading files: ${error}`} />}

                {!isLoading && !error && (
                    <>
                        <FileUpload name="project-files" accept="*" multiple value={filesToUpload} onChange={handleFileUploadChange} onValidate={handleValidateFileSizes} />
                        {artifacts.length > 0 && (
                            <div className="mt-4 min-h-0 flex-1 overflow-y-auto border-t">
                                <div className="border-r border-l">
                                    {sortedArtifacts.map(artifact => {
                                        const isExpanded = expandedArtifact === artifact.filename;
                                        const expandedContent = isExpanded ? <FileDetails description={artifact.description ?? undefined} size={artifact.size} lastModified={artifact.last_modified} mimeType={artifact.mime_type} /> : undefined;

                                        return (
                                            <ArtifactBar
                                                key={artifact.filename}
                                                filename={artifact.filename}
                                                description={artifact.description || formatRelativeTime(artifact.last_modified)}
                                                mimeType={artifact.mime_type}
                                                size={artifact.size}
                                                status="completed"
                                                context="list"
                                                expandable={true}
                                                expanded={isExpanded}
                                                expandedContent={expandedContent}
                                                source="project"
                                                actions={{
                                                    onInfo: () => handleToggleExpand(artifact.filename),
                                                    onEdit: () => handleEditDescription(artifact),
                                                    onDownload: () => onDownload(artifact),
                                                    onDelete: () => handleDeleteClick(artifact),
                                                }}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>

            <AddProjectFilesDialog isOpen={!!filesToUpload} files={filesToUpload} onClose={handleCloseUploadDialog} onConfirm={handleConfirmUpload} isSubmitting={isSubmitting} error={uploadError} onClearError={handleClearUploadError} />

            <EditFileDescriptionDialog isOpen={showEditDialog} artifact={selectedArtifact} onClose={handleCloseEditDialog} onSave={handleSaveDescription} isSaving={isSavingMetadata} />

            <ConfirmationDialog
                title="Delete Project File"
                content={
                    fileToDelete ? (
                        <>
                            This action cannot be undone. This file will be permanently removed from the project: <strong>{fileToDelete.filename}</strong>
                        </>
                    ) : null
                }
                actionLabels={{ confirm: "Delete" }}
                open={!!fileToDelete}
                onConfirm={handleConfirmDelete}
                onOpenChange={open => !open && setFileToDelete(null)}
            />
        </div>
    );
};
