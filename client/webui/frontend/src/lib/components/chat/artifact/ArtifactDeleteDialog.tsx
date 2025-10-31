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
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">
                        Delete
                        <span className="inline-block truncate" title={artifactToDelete.filename}>
                            <code>{artifactToDelete.filename}</code>
                        </span>
                        ?
                    </DialogTitle>
                    <DialogDescription className="flex flex-col gap-2">
                        <div>
                            {artifactToDelete.source === 'project'
                                ? 'This will remove the file from this chat session. The file will remain in the project.'
                                : 'This file will be permanently deleted.'
                            }
                        </div>
                    </DialogDescription>
                </DialogHeader>
                <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={closeDeleteModal}>
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
