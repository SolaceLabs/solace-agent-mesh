import React, { useState, useEffect } from "react";
import { Plus, RefreshCcw } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { CreateProjectDialog } from "./CreateProjectDialog";
import { ProjectListSidebar } from "./ProjectListSidebar";
import { ProjectDetailPanel } from "./ProjectDetailPanel";
import { ProjectMetadataSidebar } from "./ProjectMetadataSidebar";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";

interface ProjectsPageProps {
    onProjectActivated: () => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onProjectActivated }) => {
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [isCreating, setIsCreating] = useState(false);

    const {
        projects,
        isLoading,
        error,
        createProject,
        deleteProject,
        selectedProject,
        setSelectedProject,
        setActiveProject,
        refetch,
    } = useProjectContext();
    const { handleSwitchSession, handleNewSession } = useChatContext();

    // Use React Router's useSearchParams for URL-based navigation (if available)
    let searchParams: URLSearchParams | null = null;
    let setSearchParams: ((params: URLSearchParams) => void) | null = null;
    try {
        [searchParams, setSearchParams] = useSearchParams();
    } catch (e) {
        // Router not available - will use event-based navigation only
        console.debug("Router not available, using event-based navigation only");
    }

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
            // Auto-select the newly created project
            setSelectedProject(newProject);
        } finally {
            setIsCreating(false);
        }
    };

    const handleProjectSelect = (project: Project) => {
        setSelectedProject(project);
    };

    const handleCreateNew = () => {
        setShowCreateDialog(true);
    };

    const handleChatClick = async (sessionId: string) => {
        // Switch to the session first, which will activate the project automatically
        await handleSwitchSession(sessionId);
        onProjectActivated();
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

    // Handle URL-based navigation for apps using React Router (e.g., enterprise app with HashRouter)
    // Reads projectId from URL params and auto-selects the project
    useEffect(() => {
        if (searchParams && projects.length > 0) {
            const projectId = searchParams.get("projectId");
            if (projectId) {
                const project = projects.find(p => p.id === projectId);
                if (project) {
                    setSelectedProject(project);

                    if (setSearchParams) {
                        const newParams = new URLSearchParams(searchParams);
                        newParams.delete("projectId");
                        setSearchParams(newParams);
                    }
                }
            }
        }
    }, [searchParams, projects, setSelectedProject, setSearchParams]);

    // Handle event-based navigation for apps using state-based routing (Community)
    // Listens for navigate-to-project events and selects the project
    useEffect(() => {
        const handleNavigateToProject = (event: CustomEvent) => {
            const { projectId } = event.detail;
            const project = projects.find(p => p.id === projectId);
            if (project) {
                setSelectedProject(project);
            }
        };

        window.addEventListener("navigate-to-project", handleNavigateToProject as EventListener);
        return () => {
            window.removeEventListener("navigate-to-project", handleNavigateToProject as EventListener);
        };
    }, [projects, setSelectedProject]);

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Projects"
                buttons={[
                    <Button key="create-project" variant="outline" onClick={handleCreateNew} className="flex items-center gap-2">
                        <Plus className="h-4 w-4" />
                        Create Project
                    </Button>,
                    <Button key="refresh-projects" data-testid="refreshProjects" disabled={isLoading} variant="ghost" title="Refresh Projects" onClick={() => refetch()}>
                        <RefreshCcw className="size-4" />
                        Refresh
                    </Button>
                ]}
            />
            <div className="flex-1 min-h-0">
                <ResizablePanelGroup direction="horizontal" className="h-full">
                    {/* Left Sidebar - Project List */}
                    <ResizablePanel
                        defaultSize={20}
                        minSize={15}
                        maxSize={30}
                        className="min-w-[200px]"
                    >
                        <ProjectListSidebar
                            projects={projects}
                            selectedProject={selectedProject}
                            isLoading={isLoading}
                            error={error}
                            onProjectSelect={handleProjectSelect}
                            onCreateNew={handleCreateNew}
                            onProjectDelete={deleteProject}
                        />
                    </ResizablePanel>

                    <ResizableHandle />

                    {/* Center Panel - Project Details */}
                    <ResizablePanel defaultSize={55} minSize={40}>
                        <ProjectDetailPanel
                            selectedProject={selectedProject}
                            onCreateNew={handleCreateNew}
                            onChatClick={handleChatClick}
                            onStartNewChat={handleStartNewChat}
                        />
                    </ResizablePanel>

                    <ResizableHandle />

                    {/* Right Sidebar - Metadata */}
                    <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
                        <ProjectMetadataSidebar selectedProject={selectedProject} />
                    </ResizablePanel>
                </ResizablePanelGroup>
            </div>
            
            {/* Simple Create Dialog */}
            <CreateProjectDialog
                isOpen={showCreateDialog}
                onClose={() => setShowCreateDialog(false)}
                onSubmit={handleCreateProject}
                isSubmitting={isCreating}
            />
        </div>
    );
};
