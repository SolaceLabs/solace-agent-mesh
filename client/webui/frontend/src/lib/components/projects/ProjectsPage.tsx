import React, { useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { ProjectDetailView } from "./ProjectDetailView";
import { ProjectList } from "./ProjectList";
import { useProjectContext } from "@/lib/providers";
import type { Project, ProjectFormData } from "@/lib/types/projects";

interface ProjectsPageProps {
    onProjectActivated: () => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onProjectActivated }) => {
    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const { projects, isLoading, error, createProject, currentProject, setCurrentProject, activeProject, setActiveProject } = useProjectContext();

    const handleCreateProject = async (data: ProjectFormData) => {
        await createProject({
            name: data.name,
            description: data.description || undefined,
        });
        setIsCreateDialogOpen(false);
    };

    const handleActivateProject = (project: Project) => {
        setActiveProject(project);
        onProjectActivated();
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-muted-foreground">Loading projects...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-destructive">Error: {error}</div>
            </div>
        );
    }

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title={currentProject ? `Project Details` : "Projects"}
                buttons={
                    !currentProject
                        ? [
                              <Button key="create-project" onClick={() => setIsCreateDialogOpen(true)} className="flex items-center gap-2">
                                  <Plus className="h-4 w-4" />
                                  Create Project
                              </Button>,
                          ]
                        : undefined
                }
            />
            <div className="flex-1 py-6 px-8">
                {currentProject ? (
                    <ProjectDetailView
                        project={currentProject}
                        isActive={!!activeProject && activeProject.id === currentProject.id}
                        onBack={() => setCurrentProject(null)}
                        onActivate={handleActivateProject}
                    />
                ) : (
                    <>
                        <div className="mb-6">
                            <p className="text-muted-foreground">Organize your chats and sessions into projects</p>
                        </div>
                        <ProjectList projects={projects} onProjectSelect={setCurrentProject} />
                    </>
                )}

                <CreateProjectDialog isOpen={isCreateDialogOpen} onClose={() => setIsCreateDialogOpen(false)} onSubmit={handleCreateProject} />
            </div>
        </div>
    );
};
