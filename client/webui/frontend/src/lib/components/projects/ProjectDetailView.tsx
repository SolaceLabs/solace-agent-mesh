import React, { useState } from "react";
import { Pencil, Check, X, Trash2 } from "lucide-react";

import { Button, Input, Textarea } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { Header } from "@/lib/components/header";
import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { SystemPromptSection } from "./SystemPromptSection";
import { DefaultAgentSection } from "./DefaultAgentSection";
import { KnowledgeSection } from "./KnowledgeSection";
import { ProjectChatsSection } from "./ProjectChatsSection";
import { DeleteProjectDialog } from "./DeleteProjectDialog";

interface ProjectDetailViewProps {
    project: Project;
    onBack: () => void;
    onStartNewChat?: () => void;
    onChatClick?: (sessionId: string) => void;
}

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({
    project,
    onBack,
    onStartNewChat,
    onChatClick,
}) => {
    const { updateProject, projects, deleteProject } = useProjectContext();
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editedName, setEditedName] = useState(project.name);
    const [editedDescription, setEditedDescription] = useState(project.description || "");
    const [nameError, setNameError] = useState<string | null>(null);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const handleSaveSystemPrompt = async (systemPrompt: string) => {
        setError(null);
        setIsSaving(true);
        try {
            const updateData: UpdateProjectData = { systemPrompt };
            await updateProject(project.id, updateData);
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Failed to update instructions";
            setError(errorMessage);
            throw err;
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveDefaultAgent = async (defaultAgentId: string | null) => {
        setIsSaving(true);
        try {
            const updateData: UpdateProjectData = { defaultAgentId };
            await updateProject(project.id, updateData);
        } catch (err) {
            console.error("Failed to update default agent:", err);
            throw err;
        } finally {
            setIsSaving(false);
        }
    };

    const handleSave = async () => {
        const trimmedName = editedName.trim();
        const trimmedDescription = editedDescription.trim();
        
        // Check for duplicate project names (case-insensitive)
        const isDuplicate = projects.some(
            p => p.id !== project.id && p.name.toLowerCase() === trimmedName.toLowerCase()
        );
        
        if (isDuplicate) {
            setNameError("A project with this name already exists");
            return;
        }
        
        setNameError(null);
        setIsSaving(true);
        try {
            const updateData: UpdateProjectData = {};
            if (trimmedName !== project.name) {
                updateData.name = trimmedName;
            }
            if (trimmedDescription !== (project.description || "")) {
                updateData.description = trimmedDescription;
            }
            
            if (Object.keys(updateData).length > 0) {
                await updateProject(project.id, updateData);
            }
            setIsEditing(false);
        } catch (err) {
            console.error("Failed to update project:", err);
            setNameError(err instanceof Error ? err.message : "Failed to update project");
        } finally {
            setIsSaving(false);
        }
    };

    const handleCancelEdit = () => {
        setEditedName(project.name);
        setEditedDescription(project.description || "");
        setIsEditing(false);
        setNameError(null);
    };
    const handleDeleteClick = () => {
        setIsDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        setIsDeleting(true);
        try {
            await deleteProject(project.id);
            setIsDeleteDialogOpen(false);
            // Navigate back to list after successful deletion
            onBack();
        } catch (error) {
            console.error("Failed to delete project:", error);
        } finally {
            setIsDeleting(false);
        }
    };


    return (
        <div className="flex h-full flex-col">
            {/* Header with breadcrumbs */}
            <Header
                title={
                    isEditing ? (
                        <div className="flex items-center gap-2 w-full">
                            <Input
                                value={editedName}
                                onChange={(e) => setEditedName(e.target.value)}
                                className="text-xl font-bold"
                                disabled={isSaving}
                                placeholder="Project name"
                                maxLength={255}
                            />
                        </div>
                    ) : (
                        <div className="flex flex-col">
                            <span>{project.name}</span>
                            {project.description && (
                                <span className="text-sm font-normal text-muted-foreground">{project.description}</span>
                            )}
                        </div>
                    )
                }
                breadcrumbs={[
                    { label: "Projects", onClick: onBack },
                    { label: project.name }
                ]}
                buttons={
                    isEditing ? [
                        <Button
                            key="cancel"
                            variant="outline"
                            size="sm"
                            onClick={handleCancelEdit}
                            disabled={isSaving}
                            className="gap-1"
                        >
                            <X className="h-4 w-4" />
                            Cancel
                        </Button>,
                        <Button
                            key="save"
                            variant="default"
                            size="sm"
                            onClick={handleSave}
                            disabled={isSaving}
                            className="gap-1"
                        >
                            <Check className="h-4 w-4" />
                            Save
                        </Button>
                    ] : [
                        <Button
                            key="edit"
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setIsEditing(true);
                                setEditedName(project.name);
                                setEditedDescription(project.description || "");
                            }}
                            title="Edit project"
                        >
                            <Pencil className="h-4 w-4" />
                        </Button>,
                        <Button
                            key="delete"
                            variant="ghost"
                            size="sm"
                            onClick={handleDeleteClick}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            title="Delete project"
                        >
                            <Trash2 className="h-4 w-4" />
                        </Button>
                    ]
                }
            />

            {/* Edit mode description and errors */}
            {isEditing && (
                <div className="border-b px-8 py-4 space-y-3">
                    <div>
                        <Textarea
                            value={editedDescription}
                            onChange={(e) => setEditedDescription(e.target.value)}
                            className="text-sm resize-none"
                            placeholder="Project description (optional)"
                            rows={3}
                            disabled={isSaving}
                            maxLength={1000}
                        />
                        <div className="mt-1 text-xs text-muted-foreground text-right">
                            {editedDescription.length}/1000 characters
                        </div>
                    </div>
                    {nameError && (
                        <MessageBanner variant="error" message={nameError} />
                    )}
                </div>
            )}

            {/* Content area with left and right panels */}
            <div className="flex flex-1 min-h-0">
                {/* Left Panel - Project Chats */}
                <div className="w-[60%] overflow-y-auto border-r">

                    {/* Project Chats in main area */}
                    <div className="p-6">
                        {onChatClick && (
                            <ProjectChatsSection
                                project={project}
                                onChatClick={onChatClick}
                                onStartNewChat={onStartNewChat}
                            />
                        )}
                    </div>
                </div>

                {/* Right Panel - Metadata Sidebar */}
                <div className="w-[40%] overflow-y-auto bg-muted/30 pt-6">
                    <SystemPromptSection
                        project={project}
                        onSave={handleSaveSystemPrompt}
                        isSaving={isSaving}
                        error={error}
                    />

                    <DefaultAgentSection
                        project={project}
                        onSave={handleSaveDefaultAgent}
                        isSaving={isSaving}
                    />

                    <KnowledgeSection project={project} />
                </div>
            </div>

            <DeleteProjectDialog
                isOpen={isDeleteDialogOpen}
                onClose={() => setIsDeleteDialogOpen(false)}
                onConfirm={handleDeleteConfirm}
                project={project}
                isDeleting={isDeleting}
            />
        </div>
    );
};