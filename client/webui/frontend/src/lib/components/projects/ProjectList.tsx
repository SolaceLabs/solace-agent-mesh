import React from "react";

import { ProjectCard } from "./ProjectCard";
import type { Project } from "@/lib/types/projects";

interface ProjectListProps {
    projects: Project[];
    onProjectSelect?: (project: Project) => void;
}

export const ProjectList: React.FC<ProjectListProps> = ({ projects, onProjectSelect }) => {
    if (projects.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="space-y-3">
                    <h3 className="text-lg font-medium text-foreground">No projects yet</h3>
                    <p className="text-sm text-muted-foreground max-w-md">
                        Create your first project to get started organizing your chats and sessions.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {projects.map((project) => (
                <ProjectCard
                    key={project.id}
                    project={project}
                    onClick={onProjectSelect ? () => onProjectSelect(project) : undefined}
                />
            ))}
        </div>
    );
};