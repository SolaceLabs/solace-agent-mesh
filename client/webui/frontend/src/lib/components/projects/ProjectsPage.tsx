import React, { useState, useEffect } from "react";
import { RefreshCcw } from "lucide-react";

import { CreateProjectDialog } from "./CreateProjectDialog";
import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { ProjectsListView } from "./ProjectsListView";
import { ProjectDetailView } from "./ProjectDetailView";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";

interface ProjectsPageProps {
    onProjectActivated: () => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onProjectActivated }) => {
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const {
        isLoading,
        createProject,
        selectedProject,
        setSelectedProject,
        setActiveProject,
        refetch,
        searchQuery,
        setSearchQuery,
        filteredProjects,
        deleteProject,
    } = useProjectContext();
    const { handleNewSession, handleSwitchSession } = useChatContext();

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
            
            // Auto-select the newly created project
            setSelectedProject(newProject);
        } finally {
            setIsCreating(false);
        }
    };

    const handleProjectSelect = (project: Project) => {
        setSelectedProject(project);
    };

    const handleBackToList = () => {
        setSelectedProject(null);
    };

    const handleChatClick = async (sessionId: string) => {

        if (selectedProject) {
            setActiveProject(selectedProject);
        }
        await handleSwitchSession(sessionId);
        onProjectActivated();
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

    const handleStartNewChat = async () => {
        // Activate the project and start a new chat session
        if (selectedProject) {
            setActiveProject(selectedProject);
            // Start a new session while preserving the active project context
            await handleNewSession(true);
            // Navigate to chat page
            onProjectActivated();
            // Dispatch focus event after navigation to ensure ChatInputArea is mounted
            setTimeout(() => {
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("focus-chat-input"));
                }
            }, 150);
        }
    };

    // Handle event-based navigation for state-based routing
    // Listens for navigate-to-project events and selects the project
    useEffect(() => {
        const handleNavigateToProject = (event: CustomEvent) => {
            const { projectId } = event.detail;
            const project = filteredProjects.find(p => p.id === projectId);
            if (project) {
                setSelectedProject(project);
            }
        };

        window.addEventListener("navigate-to-project", handleNavigateToProject as EventListener);
        return () => {
            window.removeEventListener("navigate-to-project", handleNavigateToProject as EventListener);
        };
    }, [filteredProjects, setSelectedProject]);

    // Determine if we should show list or detail view
    const showDetailView = selectedProject !== null;

    return (
        <div className="flex h-full w-full flex-col">
            {!showDetailView && (
                <Header
                    title="Projects"
                    buttons={[
                        <Button key="refresh-projects" data-testid="refreshProjects" disabled={isLoading} variant="ghost" title="Refresh Projects" onClick={() => refetch()}>
                            <RefreshCcw className="size-4" />
                            Refresh
                        </Button>
                    ]}
                />
            )}
            
            <div className="flex-1 min-h-0">
                {showDetailView ? (
                    <ProjectDetailView
                        project={selectedProject}
                        onBack={handleBackToList}
                        onStartNewChat={handleStartNewChat}
                        onChatClick={handleChatClick}
                    />
                ) : (
                    <ProjectsListView
                        projects={filteredProjects}
                        searchQuery={searchQuery}
                        onSearchChange={setSearchQuery}
                        onProjectClick={handleProjectSelect}
                        onCreateNew={handleCreateNew}
                        onDelete={handleDeleteClick}
                        isLoading={isLoading}
                    />
                )}
            </div>
            
            {/* Create Project Dialog */}
            <CreateProjectDialog
                isOpen={showCreateDialog}
                onClose={() => setShowCreateDialog(false)}
                onSubmit={handleCreateProject}
                isSubmitting={isCreating}
            />

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
