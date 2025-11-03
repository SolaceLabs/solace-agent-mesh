import React, { useState } from "react";
import { FolderOpen, Plus } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { ProjectHeader } from "./ProjectHeader";
import { ProjectDescription } from "./ProjectDescription";
import { ProjectChatsSection } from "./ProjectChatsSection";

interface ProjectDetailPanelProps {
    selectedProject: Project | null;
    onCreateNew?: () => void;
    onChatClick?: (sessionId: string) => void;
    onStartNewChat?: () => void;
}

export const ProjectDetailPanel: React.FC<ProjectDetailPanelProps> = ({
    selectedProject,
    onCreateNew,
    onChatClick,
    onStartNewChat,
}) => {
    const { updateProject } = useProjectContext();
    const [isEditingName, setIsEditingName] = useState(false);
    const [isEditingDescription, setIsEditingDescription] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // Placeholder state
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

    const handleSaveName = async (name: string) => {
        setIsSaving(true);
        try {
            const updateData: UpdateProjectData = { name };
            await updateProject(selectedProject.id, updateData);
            setIsEditingName(false);
        } catch (error) {
            console.error("Failed to update project name:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveDescription = async (description: string) => {
        setIsSaving(true);
        try {
            const updateData: UpdateProjectData = { description };
            await updateProject(selectedProject.id, updateData);
            setIsEditingDescription(false);
        } catch (error) {
            console.error("Failed to update project description:", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleChatClick = (sessionId: string) => {
        if (onChatClick) {
            onChatClick(sessionId);
        }
    };

    return (
        <div className="flex h-full flex-col bg-background overflow-y-auto">
            <ProjectHeader
                project={selectedProject}
                isEditing={isEditingName}
                onToggleEdit={() => setIsEditingName(!isEditingName)}
                onSave={handleSaveName}
                isSaving={isSaving}
            />

            <ProjectDescription
                project={selectedProject}
                isEditing={isEditingDescription}
                onToggleEdit={() => setIsEditingDescription(!isEditingDescription)}
                onSave={handleSaveDescription}
                isSaving={isSaving}
            />

            <ProjectChatsSection
                project={selectedProject}
                onChatClick={handleChatClick}
                onStartNewChat={onStartNewChat}
            />
        </div>
    );
};
