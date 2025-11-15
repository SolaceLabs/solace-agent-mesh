import React, { useState, useEffect } from "react";
import { RefreshCcw, Download } from "lucide-react";

import { CreateProjectDialog } from "./CreateProjectDialog";
import { DeleteProjectDialog } from "./DeleteProjectDialog";
import { ProjectImportDialog } from "./ProjectImportDialog";
import { ProjectCards } from "./ProjectCards";
import { ProjectDetailView } from "./ProjectDetailView";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";
import { authenticatedFetch } from "@/lib/utils/api";

interface ProjectsPageProps {
    onProjectActivated: () => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onProjectActivated }) => {
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);
    const [showImportDialog, setShowImportDialog] = useState(false);

    const { isLoading, createProject, selectedProject, setSelectedProject, setActiveProject, refetch, searchQuery, setSearchQuery, filteredProjects, deleteProject } = useProjectContext();
    const { handleNewSession, handleSwitchSession, addNotification } = useChatContext();

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

    const handleExport = async (project: Project) => {
        try {
            const response = await authenticatedFetch(
                `/api/v1/projects/${project.id}/export`,
                { credentials: "include" }
            );
            
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `project-${project.name.replace(/[^a-z0-9]/gi, "-").toLowerCase()}-${Date.now()}.zip`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                addNotification("Project exported successfully", "success");
            } else {
                const error = await response.json();
                const errorMessage = error.detail || "Failed to export project";
                addNotification(errorMessage, "error");
            }
        } catch (error) {
            console.error("Failed to export project:", error);
            addNotification("Failed to export project", "error");
        }
    };

    const handleImport = async (file: File, options: { preserveName: boolean; customName?: string }) => {
        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("options", JSON.stringify(options));
            
            const response = await authenticatedFetch(
                "/api/v1/projects/import",
                {
                    method: "POST",
                    credentials: "include",
                    body: formData,
                }
            );
            
            if (response.ok) {
                const result = await response.json();
                
                // Show warnings if any
                if (result.warnings && result.warnings.length > 0) {
                    result.warnings.forEach((warning: string) => {
                        addNotification(warning, "info");
                    });
                }
                
                // Refresh projects and select the newly imported one
                await refetch();
                const importedProject = filteredProjects.find(p => p.id === result.projectId);
                if (importedProject) {
                    setSelectedProject(importedProject);
                }
                
                addNotification(
                    `Project imported successfully with ${result.artifactsImported} artifacts`,
                    "success"
                );
            } else {
                const error = await response.json();
                const errorMessage = error.detail || "Failed to import project";
                throw new Error(errorMessage);
            }
        } catch (error) {
            console.error("Failed to import project:", error);
            throw error; // Re-throw to let dialog handle it
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
                        <Button key="importProject" variant="ghost" title="Import Project" onClick={() => setShowImportDialog(true)}>
                            <Download className="size-4" />
                            Import Project
                        </Button>,
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
                    <ProjectCards projects={filteredProjects} searchQuery={searchQuery} onSearchChange={setSearchQuery} onProjectClick={handleProjectSelect} onCreateNew={handleCreateNew} onDelete={handleDeleteClick} onExport={handleExport} isLoading={isLoading} />
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

            {/* Import Project Dialog */}
            <ProjectImportDialog
                open={showImportDialog}
                onOpenChange={setShowImportDialog}
                onImport={handleImport}
            />
        </div>
    );
};
