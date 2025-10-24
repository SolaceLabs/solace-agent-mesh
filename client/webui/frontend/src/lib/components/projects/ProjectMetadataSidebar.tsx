import React, { useState } from "react";

import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { SystemPromptSection } from "./SystemPromptSection";
import { KnowledgeSection } from "./KnowledgeSection";

interface ProjectMetadataSidebarProps {
    selectedProject: Project | null;
}

export const ProjectMetadataSidebar: React.FC<ProjectMetadataSidebarProps> = ({
    selectedProject,
}) => {
    const { updateProject } = useProjectContext();
    const [isSaving, setIsSaving] = useState(false);

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
        try {
            const updateData: UpdateProjectData = { systemPrompt };
            await updateProject(selectedProject.id, updateData);
        } catch (error) {
            console.error("Failed to update instructions:", error);
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
            />

            <KnowledgeSection project={selectedProject} />
        </div>
    );
};
