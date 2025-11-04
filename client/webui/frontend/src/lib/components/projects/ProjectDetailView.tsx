import React, { useState } from "react";
import { ArrowLeft, Pencil, Check, X } from "lucide-react";

import { Button, Input, Textarea } from "@/lib/components/ui";
import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { SystemPromptSection } from "./SystemPromptSection";
import { DefaultAgentSection } from "./DefaultAgentSection";
import { KnowledgeSection } from "./KnowledgeSection";
import { ProjectChatsSection } from "./ProjectChatsSection";

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
    const { updateProject, projects } = useProjectContext();
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editedName, setEditedName] = useState(project.name);
    const [editedDescription, setEditedDescription] = useState(project.description || "");
    const [nameError, setNameError] = useState<string | null>(null);

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

    return (
        <div className="flex h-full">
            {/* Left Panel - Project Title and Chats */}
            <div className="w-[60%] overflow-y-auto border-r">
                <div className="sticky top-0 z-10 bg-background border-b px-6 py-4">
                    <Button
                        variant="ghost"
                        onClick={onBack}
                        className="mb-4 flex items-center gap-2 text-muted-foreground hover:text-foreground"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Back to all projects
                    </Button>
                    
                    {isEditing ? (
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <Input
                                    value={editedName}
                                    onChange={(e) => setEditedName(e.target.value)}
                                    className="text-2xl font-bold flex-1"
                                    disabled={isSaving}
                                    placeholder="Project name"
                                />
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleSave}
                                    disabled={isSaving}
                                    className="h-8 w-8 p-0"
                                >
                                    <Check className="h-4 w-4" />
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleCancelEdit}
                                    disabled={isSaving}
                                    className="h-8 w-8 p-0"
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                            <Textarea
                                value={editedDescription}
                                onChange={(e) => setEditedDescription(e.target.value)}
                                className="text-sm resize-none"
                                placeholder="Project description (optional)"
                                rows={2}
                                disabled={isSaving}
                            />
                            {nameError && (
                                <div className="text-sm text-destructive">{nameError}</div>
                            )}
                        </div>
                    ) : (
                        <div className="flex items-start gap-2">
                            <div className="flex-1 min-w-0">
                                <h1 className="text-2xl font-bold mb-1">{project.name}</h1>
                                {project.description && (
                                    <p className="text-sm text-muted-foreground">{project.description}</p>
                                )}
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setIsEditing(true);
                                    setEditedName(project.name);
                                    setEditedDescription(project.description || "");
                                }}
                                className="h-8 w-8 p-0 flex-shrink-0"
                                title="Edit project"
                            >
                                <Pencil className="h-4 w-4" />
                            </Button>
                        </div>
                    )}
                </div>

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
    );
};