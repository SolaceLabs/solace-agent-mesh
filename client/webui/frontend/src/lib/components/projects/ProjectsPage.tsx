import React, { useState, useCallback, useMemo } from "react";
import { RefreshCcw, Upload } from "lucide-react";
import { useLoaderData, useNavigate } from "react-router-dom";

import { CreateProjectDialog } from "./CreateProjectDialog";
import { ProjectImportDialog } from "./ProjectImportDialog";
import { ProjectCards } from "./ProjectCards";
import { ProjectDetailView } from "./ProjectDetailView";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";
import { useCreateProject, useProjects } from "@/features/projects/api/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { projects } from "@/features/projects/api/keys";

export const ProjectsPage: React.FC = () => {
    const navigate = useNavigate();
    const loaderData = useLoaderData<{ projectId?: string }>();

    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [showImportDialog, setShowImportDialog] = useState(false);

    const { setActiveProject } = useProjectContext();
    const [searchQuery, setSearchQuery] = useState("");
    const { handleNewSession, handleSwitchSession } = useChatContext();

    const { data, isLoading } = useProjects();
    const createProject = useCreateProject();
    const queryClient = useQueryClient();
    const selectedProject = useMemo(() => (data ? data.projects.find(p => p.id === loaderData?.projectId) : null), [data, loaderData?.projectId]);

    const filteredProjects = useMemo(() => {
        if (!data) return [];
        if (!searchQuery.trim()) return data.projects;

        const query = searchQuery.toLowerCase();
        return data.projects.filter(project => project.name.toLowerCase().includes(query) || (project.description?.toLowerCase().includes(query) ?? false));
    }, [data, searchQuery]);

    const handleCreateProject = async (data: { name: string; description: string }) => {
        setIsCreating(true);
        try {
            const formData = new FormData();
            formData.append("name", data.name);
            if (data.description) {
                formData.append("description", data.description);
            }

            await createProject.mutateAsync(formData, {
                onSuccess: data => {
                    navigate(`/projects/${data.id}`);
                    queryClient.invalidateQueries({ queryKey: projects.all.queryKey });
                },
                onSettled: () => setShowCreateDialog(false),
            });
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

    const handleStartNewChat = useCallback(async () => {
        if (selectedProject) {
            setActiveProject(selectedProject);
            // Start a new session while preserving the active project context
            handleNewSession(true);
            navigate("chat");
        }
    }, [selectedProject, setActiveProject, handleNewSession, navigate]);

    // Determine if we should show list or detail view
    const showDetailView = selectedProject !== null;

    if (!data) return;

    return (
        <div className="flex h-full w-full flex-col">
            {!selectedProject && (
                <Header
                    title="Projects"
                    buttons={[
                        <Button key="importProject" variant="ghost" title="Import Project" onClick={() => setShowImportDialog(true)}>
                            <Upload className="size-4" />
                            Import Project
                        </Button>,
                        <Button key="refreshProjects" data-testid="refreshProjects" disabled={isLoading} variant="ghost" title="Refresh Projects" onClick={() => queryClient.invalidateQueries({ queryKey: projects.all.queryKey })}>
                            <RefreshCcw className="size-4" />
                            Refresh Projects
                        </Button>,
                    ]}
                />
            )}

            <div className="min-h-0 flex-1">
                {showDetailView && selectedProject ? (
                    <ProjectDetailView project={selectedProject} onBack={handleBackToList} onStartNewChat={handleStartNewChat} onChatClick={handleChatClick} />
                ) : (
                    <ProjectCards projects={filteredProjects ?? []} searchQuery={searchQuery} onSearchChange={setSearchQuery} onProjectClick={handleProjectSelect} onCreateNew={handleCreateNew} isLoading={isLoading} />
                )}
            </div>

            {/* Create Project Dialog */}
            <CreateProjectDialog isOpen={showCreateDialog} onClose={() => setShowCreateDialog(false)} onSubmit={handleCreateProject} isSubmitting={isCreating} />

            {/* Import Project Dialog */}
            <ProjectImportDialog open={showImportDialog} onOpenChange={setShowImportDialog} />
        </div>
    );
};
