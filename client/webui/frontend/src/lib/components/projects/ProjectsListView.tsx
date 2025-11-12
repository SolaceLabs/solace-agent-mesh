import React from "react";
import { FolderOpen } from "lucide-react";

import { ProjectCard } from "./ProjectCard";
import { CreateProjectCard } from "./CreateProjectCard";
import type { Project } from "@/lib/types/projects";
import { EmptyState } from "../common";
import { SearchInput } from "@/lib/components/ui";

const ProjectImage = <FolderOpen className="text-muted-foreground" size={64} />;

interface ProjectsListViewProps {
    projects: Project[];
    searchQuery: string;
    onSearchChange: (query: string) => void;
    onProjectClick: (project: Project) => void;
    onCreateNew: () => void;
    onDelete: (project: Project) => void;
    isLoading?: boolean;
}

export const ProjectsListView: React.FC<ProjectsListViewProps> = ({ projects, searchQuery, onSearchChange, onProjectClick, onCreateNew, onDelete, isLoading = false }) => {
    return (
        <div className="bg-background flex h-full flex-col">
            {/* Search Bar */}
            <div className="flex h-full flex-col pt-6 pb-6 pl-6">
                <SearchInput value={searchQuery} onChange={onSearchChange} placeholder="Filter by name..." className="mb-4 w-xs" />

                {/* Projects Grid */}
                {isLoading ? (
                    <EmptyState variant="loading" title="Loading projects..." />
                ) : projects.length === 0 && searchQuery ? (
                    <EmptyState variant="notFound" title="No Projects Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => onSearchChange("") }]} />
                ) : projects.length === 0 ? (
                    <EmptyState
                        image={ProjectImage}
                        title="No Projects Found"
                        subtitle="Create projects to group related chat sessions and knowledge artifacts together."
                        buttons={[{ text: "Create New Project", variant: "default", onClick: () => onCreateNew() }]}
                    />
                ) : (
                    <div className="flex-1 overflow-y-auto">
                        <div className="flex flex-wrap gap-6">
                            <CreateProjectCard onClick={onCreateNew} />
                            {projects.map(project => (
                                <ProjectCard key={project.id} project={project} onClick={() => onProjectClick(project)} onDelete={onDelete} />
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
