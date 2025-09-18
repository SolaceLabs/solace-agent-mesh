import React, { useEffect } from "react";

import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";

export const ArtifactDeleteAllDialog: React.FC = () => {
    const { artifacts, isBatchDeleteModalOpen, setIsBatchDeleteModalOpen, confirmBatchDeleteArtifacts, setSelectedArtifactFilenames } = useChatContext();

    useEffect(() => {
        if (!isBatchDeleteModalOpen) {
            return;
        }

        setSelectedArtifactFilenames(new Set(artifacts.map(artifact => artifact.filename)));
    }, [artifacts, isBatchDeleteModalOpen, setSelectedArtifactFilenames]);

    if (!isBatchDeleteModalOpen) {
        return null;
    }

    return (
        <Dialog open={isBatchDeleteModalOpen} onOpenChange={setIsBatchDeleteModalOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete All?</DialogTitle>
                    <DialogDescription>{artifacts.length === 1 ? "One file" : `All ${artifacts.length} files`} will be permanently deleted.</DialogDescription>
                </DialogHeader>
                <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={() => setIsBatchDeleteModalOpen(false)}>
                        Cancel
                    </Button>
                    <Button variant="default" onClick={() => confirmBatchDeleteArtifacts()}>
                        Delete
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
