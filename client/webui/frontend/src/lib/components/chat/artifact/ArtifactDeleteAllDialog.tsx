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

    const hasProjectArtifacts = artifacts.some(artifact => artifact.source === 'project');
    const projectArtifactsCount = artifacts.filter(artifact => artifact.source === 'project').length;
    const regularArtifactsCount = artifacts.length - projectArtifactsCount;

    const getDescription = () => {
        if (hasProjectArtifacts && regularArtifactsCount === 0) {
            // All are project artifacts
            return `${artifacts.length === 1 ? 'This file' : `All ${artifacts.length} files`} will be removed from this chat session. ${artifacts.length === 1 ? 'The file' : 'These files'} will remain in ${artifacts.length === 1 ? 'the' : 'their'} project${artifacts.length === 1 ? '' : 's'}.`;
        } else if (hasProjectArtifacts && regularArtifactsCount > 0) {
            // Mixed: some project, some regular
            return `${regularArtifactsCount} ${regularArtifactsCount === 1 ? 'file' : 'files'} will be permanently deleted. ${projectArtifactsCount} project ${projectArtifactsCount === 1 ? 'file' : 'files'} will be removed from this chat but will remain in ${projectArtifactsCount === 1 ? 'the' : 'their'} project${projectArtifactsCount === 1 ? '' : 's'}.`;
        } else {
            // All are regular artifacts
            return `${artifacts.length === 1 ? 'One file' : `All ${artifacts.length} files`} will be permanently deleted.`;
        }
    };

    return (
        <Dialog open={isBatchDeleteModalOpen} onOpenChange={setIsBatchDeleteModalOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete All?</DialogTitle>
                    <DialogDescription>{getDescription()}</DialogDescription>
                </DialogHeader>
                <div className="flex justify-end space-x-2">
                    <Button variant="ghost" onClick={() => setIsBatchDeleteModalOpen(false)}>
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
