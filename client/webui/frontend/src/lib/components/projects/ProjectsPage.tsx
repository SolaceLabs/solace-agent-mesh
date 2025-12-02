import React, { useState, useCallback, useMemo } from "react";
import { RefreshCcw, Upload } from "lucide-react";
import { useLoaderData, useNavigate } from "react-router-dom";

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
import { fetchJsonWithError, fetchWithError, getErrorMessage } from "@/lib/utils/api";
import { downloadBlob } from "@/lib/utils/download";

export const ProjectsPage: React.FC = () => {
    const navigate = useNavigate();
    const loaderData = useLoaderData<{ projectId?: string }>();

    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);
    const [showImportDialog, setShowImportDialog] = useState(false);

    const { projects, isLoading, createProject, setActiveProject, refetch, searchQuery, setSearchQuery, filteredProjects, deleteProject } = useProjectContext();
    const { handleNewSession, handleSwitchSession, addNotification, displayError } = useChatContext();
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

    const handleExport = async (project: Project) => {
        try {
            const response = await fetchWithError(`/api/v1/projects/${project.id}/export`);
            const blob = await response.blob();
            const filename = `project-${project.name.replace(/[^a-z0-9]/gi, "-").toLowerCase()}-${Date.now()}.zip`;
            downloadBlob(blob, filename);

            addNotification("Project exported", "success");
        } catch (error) {
            console.error("Failed to export project:", error);
            displayError({ title: "Failed to Export Project", error: getErrorMessage(error, "An unknown error occurred while exporting the project.") });
        }
    };

    const handleImport = async (file: File, options: { preserveName: boolean; customName?: string }) => {
        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("options", JSON.stringify(options));

            const result = await fetchJsonWithError("/api/v1/projects/import", {
                method: "POST",
                body: formData,
            });

            // Show warnings if any (combine into single notification for better UX)
            if (result.warnings && result.warnings.length > 0) {
                const warningMessage = result.warnings.length === 1 ? result.warnings[0] : `Import completed with ${result.warnings.length} warnings:\n${result.warnings.join("\n")}`;
                addNotification(warningMessage, "info");
            }

            // Refresh projects and navigate to the newly imported one
            await refetch();
            navigate(`/projects/${result.projectId}`);
            addNotification(`Project imported with ${result.artifactsImported} artifacts`, "success");
        } catch (error) {
            console.error("Failed to import project:", error);
            throw error; // Re-throw to let dialog handle it
        }
    };

    // Determine if we should show list or detail view
    const showDetailView = selectedProject !== null;

    return (
        <div className="flex h-full w-full flex-col">
            {!showDetailView && (
                <Header
                    title="Projects"
                    buttons={[
                        <Button key="importProject" variant="ghost" title="Import Project" onClick={() => setShowImportDialog(true)}>
                            <Upload className="size-4" />
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
                    <ProjectCards
                        projects={filteredProjects}
                        searchQuery={searchQuery}
                        onSearchChange={setSearchQuery}
                        onProjectClick={handleProjectSelect}
                        onCreateNew={handleCreateNew}
                        onDelete={handleDeleteClick}
                        onExport={handleExport}
                        isLoading={isLoading}
                    />
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
            <ProjectImportDialog open={showImportDialog} onOpenChange={setShowImportDialog} onImport={handleImport} />
        </div>
    );
};
