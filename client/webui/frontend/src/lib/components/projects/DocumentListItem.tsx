import React, { useState } from "react";
import { Download, Trash, Pencil } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { formatBytes, formatRelativeTime } from "@/lib/utils/format";
import type { ArtifactInfo, Project } from "@/lib/types";
import { getFileIcon } from "../chat/file/fileUtils";
import { ConfirmationDialog } from "../common";
import { useRemoveFileFromProject, useUpdateFileMetadata } from "@/features/projects/api/hooks";
import { EditFileDescriptionDialog } from "./EditFileDescriptionDialog";
import { FileDetailsDialog } from "./FileDetailsDialog";

interface DocumentListItemProps {
    project: Project;
    artifact: ArtifactInfo;
    onDownload: () => void;
}

export const DocumentListItem: React.FC<DocumentListItemProps> = ({ project, artifact, onDownload }) => {
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [showDetailsDialog, setShowDetailsDialog] = useState(false);

    const removeFileFromProject = useRemoveFileFromProject(project.id, artifact.filename);
    const updateFileMetadata = useUpdateFileMetadata(project.id, artifact.filename);

    const handleFileDetailsEdit = () => {
        setShowEditDialog(true);
        setShowDetailsDialog(false);
    };

    return (
        <>
            <ConfirmationDialog
                title="Delete Project File"
                content={
                    <>
                        This action cannot be undone. This file will be permanently removed from the project: <strong>{artifact.filename}</strong>
                    </>
                }
                actionLabels={{ confirm: "Delete" }}
                open={showDeleteDialog}
                onConfirm={() => removeFileFromProject.mutate()}
                onOpenChange={setShowDeleteDialog}
            />

            <FileDetailsDialog isOpen={showDetailsDialog} artifact={artifact} onClose={() => setShowDetailsDialog(false)} onEdit={handleFileDetailsEdit} />

            <EditFileDescriptionDialog
                isOpen={showEditDialog}
                artifact={artifact}
                onClose={() => setShowEditDialog(false)}
                onSave={async description => {
                    await updateFileMetadata.mutateAsync(description, {
                        onSuccess: () => setShowEditDialog(false),
                    });
                }}
            />

            <div className="hover:bg-accent/50 group flex cursor-pointer items-center justify-between rounded-md p-2" onClick={() => setShowDetailsDialog(true)}>
                <div className="flex min-w-0 flex-1 items-center gap-2">
                    {getFileIcon(artifact, "h-4 w-4 flex-shrink-0 text-muted-foreground")}
                    <div className="min-w-0 flex-1">
                        <p className="text-foreground truncate text-sm font-medium" title={artifact.filename}>
                            {artifact.filename}
                        </p>
                        <div className="text-muted-foreground flex items-center gap-2 text-xs">
                            {artifact.last_modified && (
                                <span className="truncate" title={formatRelativeTime(artifact.last_modified)}>
                                    {formatRelativeTime(artifact.last_modified)}
                                </span>
                            )}
                            {artifact.size !== undefined && (
                                <>
                                    {artifact.last_modified && <span>•</span>}
                                    <span>{formatBytes(artifact.size)}</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <Button
                        variant="ghost"
                        onClick={e => {
                            e.stopPropagation();
                            setShowEditDialog(true);
                        }}
                        tooltip="Edit Description"
                    >
                        <Pencil />
                    </Button>

                    <Button
                        variant="ghost"
                        onClick={e => {
                            e.stopPropagation();
                            onDownload();
                        }}
                        tooltip="Download"
                    >
                        <Download />
                    </Button>

                    <Button
                        variant="ghost"
                        tooltip="Delete"
                        onClick={e => {
                            e.stopPropagation();
                            setShowDeleteDialog(true);
                        }}
                    >
                        <Trash />
                    </Button>
                </div>
            </div>
        </>
    );
};
