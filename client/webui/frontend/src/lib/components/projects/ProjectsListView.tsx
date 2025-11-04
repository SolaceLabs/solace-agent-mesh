import React from "react";
import { FolderOpen, Plus } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { ProjectCard } from "./ProjectCard";
import type { Project } from "@/lib/types/projects";

interface ProjectsListViewProps {
    projects: Project[];
    searchQuery: string;
    onSearchChange: (query: string) => void;
    onProjectClick: (project: Project) => void;
    onCreateNew: () => void;
    isLoading?: boolean;
}

export const ProjectsListView: React.FC<ProjectsListViewProps> = ({
    projects,
    searchQuery,
    onSearchChange,
    onProjectClick,
    onCreateNew,
    isLoading = false,
}) => {
    return (
        <div className="flex h-full flex-col bg-background">
            {/* Search Bar - matching agents page style */}
            <div className="h-full w-full pt-12 pl-12">
                <input
                    type="text"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="bg-background mb-4 rounded-md border px-3 py-2"
                />

                {/* Projects Grid - matching agents page layout */}
                {isLoading ? (
                    <div className="flex items-center justify-center p-12">
                        <div className="text-center">
                            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
                            <p className="text-sm text-muted-foreground">Loading projects...</p>
                        </div>
                    </div>
                ) : projects.length === 0 && !searchQuery ? (
                    <div className="flex flex-col items-center justify-center p-12 text-center">
                        <FolderOpen className="mb-4 h-16 w-16 text-muted-foreground" />
                        <h3 className="mb-2 text-lg font-semibold text-foreground">No projects yet</h3>
                        <p className="mb-4 text-sm text-muted-foreground">Create your first project to get started</p>
                        <Button onClick={onCreateNew}>
                            <Plus className="mr-2 h-4 w-4" />
                            Create Project
                        </Button>
                    </div>
                ) : projects.length === 0 && searchQuery ? (
                    <div className="flex flex-col items-center justify-center p-12 text-center">
                        <FolderOpen className="mb-4 h-16 w-16 text-muted-foreground" />
                        <h3 className="mb-2 text-lg font-semibold text-foreground">No projects found</h3>
                        <p className="mb-4 text-sm text-muted-foreground">Try adjusting your search terms</p>
                        <Button onClick={() => onSearchChange("")} variant="default">
                            Clear Search
                        </Button>
                    </div>
                ) : (
                    <div className="max-h-[calc(100vh-250px)] overflow-y-auto">
                        <div className="flex flex-wrap gap-10">
                            {projects.map((project) => (
                                <ProjectCard
                                    key={project.id}
                                    project={project}
                                    onClick={() => onProjectClick(project)}
                                />
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};