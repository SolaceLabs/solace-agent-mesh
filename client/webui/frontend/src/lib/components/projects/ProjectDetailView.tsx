import React, { useState } from "react";
import { Pencil, Trash2, MoreHorizontal } from "lucide-react";

import { Button, Input, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Textarea } from "@/lib/components/ui";
import { FieldFooter } from "@/lib/components/ui/fieldFooter";
import { MessageBanner, Footer } from "@/lib/components/common";
import { Header } from "@/lib/components/header";
import { useProjectContext } from "@/lib/providers";
import { useConfigContext } from "@/lib/hooks";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { DEFAULT_MAX_DESCRIPTION_LENGTH } from "@/lib/constants/validation";

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

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({ project, onBack, onStartNewChat, onChatClick }) => {
    const { updateProject, projects, deleteProject } = useProjectContext();
    const { validationLimits } = useConfigContext();
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editedName, setEditedName] = useState(project.name);
    const [editedDescription, setEditedDescription] = useState(project.description || "");
    const [nameError, setNameError] = useState<string | null>(null);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const MAX_DESCRIPTION_LENGTH = validationLimits?.projectDescriptionMax ?? DEFAULT_MAX_DESCRIPTION_LENGTH;
    const isDescriptionOverLimit = editedDescription.length > MAX_DESCRIPTION_LENGTH;

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
        const isDuplicate = projects.some(p => p.id !== project.id && p.name.toLowerCase() === trimmedName.toLowerCase());

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
            {/* Header with breadcrumbs and actions */}
            <Header
                title={project.name}
                breadcrumbs={[{ label: "Projects", onClick: onBack }, { label: project.name }]}
                buttons={[
                    <Button key="edit" variant="ghost" size="sm" onClick={() => setIsEditing(true)} testid="editDetailsButton" className="gap-2">
                        <Pencil className="h-4 w-4" />
                        Edit Details
                    </Button>,
                    <DropdownMenu key="more">
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={handleDeleteClick}>
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>,
                ]}
            />

            {/* Content area with left and right panels */}
            <div className="flex min-h-0 flex-1">
                {/* Left Panel - Description and Project Chats */}
                <div className="w-[60%] overflow-y-auto border-r">
                    {/* Description section */}
                    {project.description && (
                        <div className="px-8 py-4">
                            <p className="text-muted-foreground text-sm">{project.description}</p>
                        </div>
                    )}
                    {onChatClick && <ProjectChatsSection project={project} onChatClick={onChatClick} onStartNewChat={onStartNewChat} />}
                </div>

                {/* Right Panel - Metadata Sidebar */}
                <div className="flex min-h-0 w-[40%] flex-col">
                    <SystemPromptSection project={project} onSave={handleSaveSystemPrompt} isSaving={isSaving} error={error} />

                    <DefaultAgentSection project={project} onSave={handleSaveDefaultAgent} isSaving={isSaving} />

                    <KnowledgeSection project={project} />
                </div>
            </div>

            {/* Footer */}
            <Footer>
                <Button variant="outline" data-testid="closeButton" title="Close" onClick={onBack}>
                    Close
                </Button>
            </Footer>

            {/* Edit Project Dialog */}
            <Dialog open={isEditing} onOpenChange={setIsEditing}>
                <DialogContent onOpenAutoFocus={e => e.preventDefault()}>
                    <DialogHeader>
                        <DialogTitle>Edit Project Details</DialogTitle>
                        <DialogDescription>Update the name and description for this project.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Name*</label>
                            <Input value={editedName} onChange={e => setEditedName(e.target.value)} placeholder="Project name" disabled={isSaving} maxLength={255} autoFocus={false} />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Description*</label>
                            <Textarea
                                value={editedDescription}
                                onChange={e => setEditedDescription(e.target.value)}
                                placeholder="Project description"
                                rows={4}
                                disabled={isSaving}
                                maxLength={MAX_DESCRIPTION_LENGTH + 1}
                                className={`resize-none text-sm ${isDescriptionOverLimit ? "border-destructive" : ""}`}
                            />
                            <FieldFooter hasError={isDescriptionOverLimit} message={`${editedDescription.length} / ${MAX_DESCRIPTION_LENGTH}`} error={`Description must be less than ${MAX_DESCRIPTION_LENGTH} characters`} />
                        </div>
                        {nameError && <MessageBanner variant="error" message={nameError} />}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={handleCancelEdit} disabled={isSaving}>
                            Discard Changes
                        </Button>
                        <Button onClick={handleSave} disabled={isSaving || isDescriptionOverLimit}>
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Project Dialog */}
            <DeleteProjectDialog isOpen={isDeleteDialogOpen} onClose={() => setIsDeleteDialogOpen(false)} onConfirm={handleDeleteConfirm} project={project} isDeleting={isDeleting} />
        </div>
    );
};
