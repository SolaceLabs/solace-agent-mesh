import React, { useEffect } from "react";

import { useChatContext } from "@/lib/hooks";
import { ConfirmationDialog } from "../../common";

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

    const hasProjectArtifacts = artifacts.some(artifact => artifact.source === "project");
    const projectArtifactsCount = artifacts.filter(artifact => artifact.source === "project").length;
    const regularArtifactsCount = artifacts.length - projectArtifactsCount;

    const getDescription = () => {
        if (hasProjectArtifacts && regularArtifactsCount === 0) {
            // All are project artifacts
            return `${artifacts.length === 1 ? "This file" : `All ${artifacts.length} files`} will be removed from this chat session. ${artifacts.length === 1 ? "The file" : "These files"} will remain in ${artifacts.length === 1 ? "the" : "their"} project${artifacts.length === 1 ? "" : "s"}.`;
        } else if (hasProjectArtifacts && regularArtifactsCount > 0) {
            // Mixed: some project, some regular
            return `${regularArtifactsCount} ${regularArtifactsCount === 1 ? "file" : "files"} will be permanently deleted. ${projectArtifactsCount} project ${projectArtifactsCount === 1 ? "file" : "files"} will be removed from this chat but will remain in ${projectArtifactsCount === 1 ? "the" : "their"} project${projectArtifactsCount === 1 ? "" : "s"}.`;
        } else {
            // All are regular artifacts
            return `${artifacts.length === 1 ? "One file" : `All ${artifacts.length} files`} will be permanently deleted.`;
        }
    };

    return (
        <ConfirmationDialog
            title="Delete All?"
            description={getDescription()}
            actionLabels={{ confirm: "Delete" }}
            onCancel={() => setIsBatchDeleteModalOpen(false)}
            onConfirm={confirmBatchDeleteArtifacts}
            open={isBatchDeleteModalOpen}
            onOpenChange={setIsBatchDeleteModalOpen}
        />
    );
};
