import React, { useState, useCallback, useMemo } from "react";
import { RefreshCcw } from "lucide-react";
import { useLoaderData, useNavigate } from "react-router-dom";

import { CreateProjectDialog } from "./CreateProjectDialog";
import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { ProjectCards } from "./ProjectCards";
import { ProjectDetailView } from "./ProjectDetailView";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";

export const ProjectsPage: React.FC = () => {
    const navigate = useNavigate();
    const loaderData = useLoaderData<{ projectId?: string }>();

    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const { projects, isLoading, createProject, setActiveProject, refetch, searchQuery, setSearchQuery, filteredProjects, deleteProject } = useProjectContext();
    const { handleNewSession, handleSwitchSession } = useChatContext();
    const selectedProject = useMemo(() => projects.find(p => p.id === loaderData?.projectId) || null, [projects, loaderData?.projectId]);

    const handleCreateProject = async (data: { name: string; description: string }) => {
        setIsCreating(true);
        try {
            const formData = new FormData();
            formData.append("name", data.name);
            if (data.description) {
                formData.append("description", data.description);
            }

            const newProject = await createProject(formData);
            setShowCreateDialog(false);

            // Refetch projects to get artifact counts
            await refetch();

            navigate(`/projects/${newProject.id}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleProjectSelect = (project: Project) => {
        navigate(`/projects/${project.id}`);
    };

    const handleBackToList = () => {
        navigate("/projects");
    };

    const handleChatClick = async (sessionId: string) => {
        if (selectedProject) {
            setActiveProject(selectedProject);
        }
        await handleSwitchSession(sessionId);
        navigate("chat");
    };

    const handleCreateNew = () => {
        setShowCreateDialog(true);
    };

    const handleDeleteClick = (project: Project) => {
        setProjectToDelete(project);
        setIsDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!projectToDelete) return;

        setIsDeleting(true);
        try {
            await deleteProject(projectToDelete.id);
            setIsDeleteDialogOpen(false);
            setProjectToDelete(null);
        } catch (error) {
            console.error("Failed to delete project:", error);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleStartNewChat = useCallback(async () => {
        if (selectedProject) {
            setActiveProject(selectedProject);
            // Start a new session while preserving the active project context
            await handleNewSession(true);
            navigate("chat");
        }
    }, [selectedProject, setActiveProject, handleNewSession, navigate]);

    // Determine if we should show list or detail view
    const showDetailView = selectedProject !== null;

    return (
        <div className="flex h-full w-full flex-col">
            {!showDetailView && (
                <Header
                    title="Projects"
                    buttons={[
                        <Button key="refreshProjects" data-testid="refreshProjects" disabled={isLoading} variant="ghost" title="Refresh Projects" onClick={() => refetch()}>
                            <RefreshCcw className="size-4" />
                            Refresh Projects
                        </Button>,
                    ]}
                />
            )}

            <div className="min-h-0 flex-1">
                {showDetailView ? (
                    <ProjectDetailView project={selectedProject} onBack={handleBackToList} onStartNewChat={handleStartNewChat} onChatClick={handleChatClick} />
                ) : (
                    <ProjectCards projects={filteredProjects} searchQuery={searchQuery} onSearchChange={setSearchQuery} onProjectClick={handleProjectSelect} onCreateNew={handleCreateNew} onDelete={handleDeleteClick} isLoading={isLoading} />
                )}
            </div>

            {/* Create Project Dialog */}
            <CreateProjectDialog isOpen={showCreateDialog} onClose={() => setShowCreateDialog(false)} onSubmit={handleCreateProject} isSubmitting={isCreating} />

            {/* Delete Project Dialog */}
            <DeleteProjectDialog
                isOpen={isDeleteDialogOpen}
                onClose={() => {
                    setIsDeleteDialogOpen(false);
                    setProjectToDelete(null);
                }}
                onConfirm={handleDeleteConfirm}
                project={projectToDelete}
                isDeleting={isDeleting}
            />
        </div>
    );
};
