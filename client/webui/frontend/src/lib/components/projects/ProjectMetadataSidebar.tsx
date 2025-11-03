import React, { useState } from "react";

import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { SystemPromptSection } from "./SystemPromptSection";
import { DefaultAgentSection } from "./DefaultAgentSection";
import { KnowledgeSection } from "./KnowledgeSection";

interface ProjectMetadataSidebarProps {
    selectedProject: Project | null;
}

export const ProjectMetadataSidebar: React.FC<ProjectMetadataSidebarProps> = ({
    selectedProject,
}) => {
    const { updateProject } = useProjectContext();
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (!selectedProject) {
        return (
            <div className="flex h-full items-center justify-center bg-background border-l">
                <p className="text-sm text-muted-foreground px-4 text-center">
                    Select a project to view its details
                </p>
            </div>
        );
    }

    const handleSaveSystemPrompt = async (systemPrompt: string) => {
        setIsSaving(true);
        setError(null);
        try {
            const updateData: UpdateProjectData = { systemPrompt };
            await updateProject(selectedProject.id, updateData);
        } catch (error) {
            console.error("Failed to update instructions:", error);
            const errorMessage = error instanceof Error ? error.message : "Failed to update instructions";
            setError(errorMessage);
            throw error; // Re-throw so SystemPromptSection can handle it
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveDefaultAgent = async (defaultAgentId: string | null) => {
        setIsSaving(true);
        try {
            const updateData: UpdateProjectData = { defaultAgentId };
            await updateProject(selectedProject.id, updateData);
        } catch (error) {
            console.error("Failed to update default agent:", error);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="flex h-full flex-col bg-background border-l overflow-y-auto">
            <SystemPromptSection
                project={selectedProject}
                onSave={handleSaveSystemPrompt}
                isSaving={isSaving}
                error={error}
            />

            <DefaultAgentSection
                project={selectedProject}
                onSave={handleSaveDefaultAgent}
                isSaving={isSaving}
            />

            <KnowledgeSection project={selectedProject} />
        </div>
    );
};
