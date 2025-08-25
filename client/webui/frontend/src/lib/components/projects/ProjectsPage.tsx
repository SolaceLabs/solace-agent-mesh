import React, { useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { ProjectList } from "./ProjectList";
import { useProjects } from "@/lib/hooks/useProjects";
import type { Project, ProjectFormData } from "@/lib/types/projects";

interface ProjectsPageProps {
    onProjectSelect?: (project: Project) => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onProjectSelect }) => {
    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const { projects, isLoading, error, createProject } = useProjects();

    const handleCreateProject = async (data: ProjectFormData) => {
        await createProject({
            name: data.name,
            description: data.description || undefined
        });
        setIsCreateDialogOpen(false);
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
                title="Projects"
                buttons={[
                    <Button 
                        key="create-project"
                        onClick={() => setIsCreateDialogOpen(true)}
                        className="flex items-center gap-2"
                    >
                        <Plus className="h-4 w-4" />
                        Create Project
                    </Button>
                ]}
            />
            <div className="flex-1 py-6 px-8">
                <div className="mb-6">
                    <p className="text-muted-foreground">
                        Organize your chats and sessions into projects
                    </p>
                </div>

                <ProjectList 
                    projects={projects} 
                    onProjectSelect={onProjectSelect}
                />

                <CreateProjectDialog
                    isOpen={isCreateDialogOpen}
                    onClose={() => setIsCreateDialogOpen(false)}
                    onSubmit={handleCreateProject}
                />
            </div>
        </div>
    );
};