import React from "react";

import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";

export const ArtifactDeleteDialog: React.FC = () => {
    const { isDeleteModalOpen, artifactToDelete, closeDeleteModal, confirmDelete } = useChatContext();

    if (!isDeleteModalOpen || !artifactToDelete) {
        return null;
    }

    return (
        <Dialog open={isDeleteModalOpen} onOpenChange={closeDeleteModal}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete?</DialogTitle>
                    <DialogDescription>
                        The file{" "}
                        <strong>
                            <code>{artifactToDelete.filename}</code>
                        </strong>{" "}
                        will be permanently deleted.
                    </DialogDescription>
                </DialogHeader>
                <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={closeDeleteModal}>
                        Cancel
                    </Button>
                    <Button variant="default" onClick={() => confirmDelete()}>
                        Delete
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
