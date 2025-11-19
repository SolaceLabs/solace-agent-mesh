import React from "react";

import { ProjectCard } from "./ProjectCard";
import { CreateProjectCard } from "./CreateProjectCard";
import type { Project } from "@/lib/types/projects";
import { EmptyState } from "@/lib/components/common";
import { SearchInput } from "@/lib/components/ui";

interface ProjectCardsProps {
    projects: Project[];
    searchQuery: string;
    onSearchChange: (query: string) => void;
    onProjectClick: (project: Project) => void;
    onCreateNew: () => void;
    onDelete: (project: Project) => void;
    isLoading?: boolean;
}

export const ProjectCards: React.FC<ProjectCardsProps> = ({ projects, searchQuery, onSearchChange, onProjectClick, onCreateNew, onDelete, isLoading = false }) => {
    return (
        <div className="bg-background flex h-full flex-col">
            <div className="flex h-full flex-col pt-6 pb-6 pl-6">
                {projects.length > 0 || searchQuery ? <SearchInput value={searchQuery} onChange={onSearchChange} placeholder="Filter by name..." className="mb-4 w-xs" /> : null}

                {/* Projects Grid */}
                {isLoading ? (
                    <EmptyState variant="loading" title="Loading projects..." />
                ) : projects.length === 0 && searchQuery ? (
                    <EmptyState variant="notFound" title="No Projects Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => onSearchChange("") }]} />
                ) : projects.length === 0 ? (
                    <EmptyState
                        variant="noImage"
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
