import React from "react";

import { ProjectCard } from "./ProjectCard";
import { CreateProjectCard } from "./CreateProjectCard";
import type { Project } from "@/lib/types/projects";
import { EmptyState, MessageBanner } from "@/lib/components/common";
import { SearchInput } from "@/lib/components/ui";

const PROJECTS_DESCRIPTION_LINE1 = "Projects allow you to give the AI a re-usable set of context for conversations. You can upload files, select a default agent and provide custom instructions.";
const PROJECTS_DESCRIPTION_LINE2 = "When you ask a question, it will find the most relevant file and pull answers directly from it. It's great for diving into your documents through natural conversation.";
const PROJECTS_DESCRIPTION_FULL = `${PROJECTS_DESCRIPTION_LINE1} ${PROJECTS_DESCRIPTION_LINE2}`;

const ProjectsDescriptionTwoParagraphs = () => (
    <span>
        {PROJECTS_DESCRIPTION_LINE1}
        <br />
        <br />
        {PROJECTS_DESCRIPTION_LINE2}
    </span>
);

interface ProjectCardsProps {
    projects: Project[];
    searchQuery: string;
    onSearchChange: (query: string) => void;
    onProjectClick: (project: Project) => void;
    onCreateNew: () => void;
    onDelete: (project: Project) => void;
    onExport?: (project: Project) => void;
    isLoading?: boolean;
}

export const ProjectCards: React.FC<ProjectCardsProps> = ({ projects, searchQuery, onSearchChange, onProjectClick, onCreateNew, onDelete, onExport, isLoading = false }) => {
    return (
        <div className="bg-card-background flex h-full flex-col">
            <div className="flex h-full flex-col pt-6 pb-6 pl-6">
                {projects.length > 0 || searchQuery ? <SearchInput value={searchQuery} onChange={onSearchChange} placeholder="Filter by name..." className="mb-4 w-xs" testid="projectSearchInput" /> : null}

                {/* Projects Grid */}
                {isLoading ? (
                    <EmptyState variant="loading" title="Loading projects..." />
                ) : projects.length === 0 && searchQuery ? (
                    <EmptyState variant="notFound" title="No Projects Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => onSearchChange("") }]} />
                ) : projects.length === 0 ? (
                    <EmptyState variant="noImage" title="No Projects Found" subtitle={<ProjectsDescriptionTwoParagraphs />} buttons={[{ text: "Create New Project", variant: "default", onClick: () => onCreateNew() }]} />
                ) : (
                    <div className="flex-1 overflow-y-auto">
                        <MessageBanner variant="info" message={PROJECTS_DESCRIPTION_FULL} className="mr-6 mb-4" />
                        <div className="flex flex-wrap gap-6">
                            <CreateProjectCard onClick={onCreateNew} />
                            {projects.map(project => (
                                <ProjectCard key={project.id} project={project} onClick={() => onProjectClick(project)} onDelete={onDelete} onExport={onExport} />
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
