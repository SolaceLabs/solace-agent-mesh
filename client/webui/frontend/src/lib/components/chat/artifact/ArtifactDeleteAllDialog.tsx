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

    // Check for read-only artifacts (project or agent_default)
    const isReadOnlyArtifact = (artifact: { source?: string }) => artifact.source === "project" || artifact.source === "agent_default";

    const hasReadOnlyArtifacts = artifacts.some(isReadOnlyArtifact);
    const readOnlyArtifactsCount = artifacts.filter(isReadOnlyArtifact).length;
    const regularArtifactsCount = artifacts.length - readOnlyArtifactsCount;

    const getDescription = () => {
        if (hasReadOnlyArtifacts && regularArtifactsCount === 0) {
            // All are read-only artifacts (project or agent_default)
            return `${artifacts.length === 1 ? "This file" : `All ${artifacts.length} files`} will be removed from this chat session. ${artifacts.length === 1 ? "The file" : "These files"} will remain available as ${artifacts.length === 1 ? "a default" : "defaults"}.`;
        } else if (hasReadOnlyArtifacts && regularArtifactsCount > 0) {
            // Mixed: some read-only, some regular
            return `${regularArtifactsCount} ${regularArtifactsCount === 1 ? "file" : "files"} will be permanently deleted. ${readOnlyArtifactsCount} read-only ${readOnlyArtifactsCount === 1 ? "file" : "files"} will be removed from this chat but will remain available.`;
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
