import React from "react";

import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import { useChatContext } from "@/lib/hooks";

export const ArtifactDeleteDialog: React.FC = () => {
    const { isDeleteModalOpen, artifactToDelete, closeDeleteModal, confirmDelete } = useChatContext();

    if (!artifactToDelete) {
        return null;
    }

    return (
        <ConfirmationDialog
            open={isDeleteModalOpen}
            onOpenChange={closeDeleteModal}
            title="Delete File"
            content={
                artifactToDelete.source === "project" ? (
                    `This action will remove the file, "${artifactToDelete.filename}", from this chat session. This file will remain in the project.`
                ) : (
                    <div>
                        This action cannot be undone. This file will be permanently deleted: <strong>{artifactToDelete.filename}</strong>.
                    </div>
                )
            }
            actionLabels={{
                confirm: "Delete",
            }}
            onConfirm={confirmDelete}
            onCancel={closeDeleteModal}
        />
    );
};
