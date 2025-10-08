import React from "react";
import { FolderOpen, Plus } from "lucide-react";

import { Button } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";

interface ProjectDetailPanelProps {
    selectedProject: Project | null;
    onCreateNew?: () => void;
}

export const ProjectDetailPanel: React.FC<ProjectDetailPanelProps> = ({
    selectedProject,
    onCreateNew,
}) => {
    // Placeholder state - will be populated in Phase 2
    if (!selectedProject) {
        return (
            <div className="flex h-full items-center justify-center bg-background">
                <div className="text-center space-y-4">
                    <FolderOpen className="h-16 w-16 text-muted-foreground mx-auto" />
                    <div>
                        <h3 className="text-lg font-semibold text-foreground mb-2">
                            Select a project to view details
                        </h3>
                        <p className="text-sm text-muted-foreground mb-4">
                            Choose a project from the sidebar to see its details, chats, and files
                        </p>
                        {onCreateNew && (
                            <Button onClick={onCreateNew}>
                                <Plus className="h-4 w-4 mr-2" />
                                Create New Project
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // Temporary content for Phase 1 - will be replaced in Phase 2
    return (
        <div className="flex h-full flex-col bg-background p-6">
            <div className="mb-4">
                <h1 className="text-2xl font-bold text-foreground">{selectedProject.name}</h1>
                {selectedProject.description && (
                    <p className="text-sm text-muted-foreground mt-2">{selectedProject.description}</p>
                )}
            </div>
            <div className="flex-1 flex items-center justify-center">
                <p className="text-muted-foreground">
                    Project details will be displayed here in Phase 2
                </p>
            </div>
        </div>
    );
};
