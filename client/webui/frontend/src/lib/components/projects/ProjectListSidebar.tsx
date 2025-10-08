import React from "react";
import { Plus, FolderOpen } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Spinner } from "@/lib/components/ui/spinner";
import type { Project } from "@/lib/types/projects";
import { ProjectListItem } from "./ProjectListItem";

interface ProjectListSidebarProps {
    projects: Project[];
    selectedProject: Project | null;
    isLoading: boolean;
    error: string | null;
    onProjectSelect: (project: Project) => void;
    onCreateNew: () => void;
}

export const ProjectListSidebar: React.FC<ProjectListSidebarProps> = ({
    projects,
    selectedProject,
    isLoading,
    error,
    onProjectSelect,
    onCreateNew,
}) => {
    return (
        <div className="flex h-full flex-col bg-background border-r">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
                <h2 className="text-lg font-semibold text-foreground">Projects</h2>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onCreateNew}
                    className="h-8 w-8 p-0"
                    tooltip="Create New Project"
                >
                    <Plus className="h-4 w-4" />
                </Button>
            </div>

            {/* Project List */}
            <div className="flex-1 overflow-y-auto">
                {isLoading && (
                    <div className="flex items-center justify-center p-8">
                        <Spinner size="small" />
                    </div>
                )}

                {error && (
                    <div className="p-4 text-sm text-destructive">
                        Error loading projects: {error}
                    </div>
                )}

                {!isLoading && !error && projects.length === 0 && (
                    <div className="flex flex-col items-center justify-center p-8 text-center">
                        <FolderOpen className="h-12 w-12 text-muted-foreground mb-4" />
                        <p className="text-sm text-muted-foreground mb-4">
                            No projects yet
                        </p>
                        <Button onClick={onCreateNew} size="sm">
                            <Plus className="h-4 w-4 mr-2" />
                            Create Project
                        </Button>
                    </div>
                )}

                {!isLoading && !error && projects.length > 0 && (
                    <div>
                        {projects.map((project) => (
                            <ProjectListItem
                                key={project.id}
                                project={project}
                                isSelected={selectedProject?.id === project.id}
                                onClick={() => onProjectSelect(project)}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
