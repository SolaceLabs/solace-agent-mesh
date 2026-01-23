import type { ArtifactInfo } from "@/lib/types";
import { ConfirmationDialog } from "../common";
import { FileLabel } from "../chat/file/FileLabel";

type DeleteProjectFileDialogProps = {
    isOpen: boolean;
    fileToDelete: ArtifactInfo | null;
    setFileToDelete: (file: ArtifactInfo | null) => void;
    handleConfirmDelete: () => void;
};

export const DeleteProjectFileDialog = ({ isOpen, fileToDelete, handleConfirmDelete, setFileToDelete }: DeleteProjectFileDialogProps) => {
    if (!fileToDelete) {
        return null;
    }

    return (
        <ConfirmationDialog
            title="Delete Project File"
            content={
                <div className="flex flex-col gap-4">
                    This action cannot be undone. This file will be permanently removed from the project.
                    <FileLabel fileName={fileToDelete.filename} fileSize={fileToDelete.size} />
                </div>
            }
            actionLabels={{ confirm: "Delete" }}
            open={isOpen}
            onConfirm={handleConfirmDelete}
            onOpenChange={open => !open && setFileToDelete(null)}
        />
    );
};
