import { ProjectCard } from "./ProjectCard";
import { CreateProjectCard } from "./CreateProjectCard";
import type { Project } from "@/lib/types/projects";
import { EmptyState, OnboardingBanner } from "@/lib/components/common";
import { SearchInput } from "@/lib/components/ui";

const PROJECTS_ONBOARDING_DISMISSED_KEY = "sam-project-onboarding-dismissed";
const PROJECTS_DESCRIPTION_LINE0 = "Projects allow you to give the AI a re-usable set of context for conversations.";
const PROJECTS_DESCRIPTION_LINE1 = "You can upload files, select a default agent and provide custom instructions.";
const PROJECTS_DESCRIPTION_LINE2 = "When you ask a question, it will find the most relevant file and pull answers directly from it. It's great for diving into your documents through natural conversation.";

const ProjectsDescriptionTwoParagraphs = () => (
    <span>
        {PROJECTS_DESCRIPTION_LINE0 + " " + PROJECTS_DESCRIPTION_LINE1}
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
    onShare?: (project: Project) => void;
    onTogglePin?: (project: Project) => void;
    isPinToggling?: boolean;
}

export const ProjectCards = ({ projects, searchQuery, onSearchChange, onProjectClick, onCreateNew, onDelete, onExport, isLoading = false, onShare, onTogglePin, isPinToggling }: ProjectCardsProps) => {
    return (
        <div className="flex h-full flex-col">
            <div className="flex h-full flex-col px-4 py-4 sm:pt-6 sm:pr-0 sm:pb-6 sm:pl-6">
                <OnboardingBanner
                    storageKey={PROJECTS_ONBOARDING_DISMISSED_KEY}
                    header={PROJECTS_DESCRIPTION_LINE0}
                    description={`${PROJECTS_DESCRIPTION_LINE1} ${PROJECTS_DESCRIPTION_LINE2}`}
                    learnMoreText={"Learn more about projects."}
                    learnMoreUrl={"https://solacelabs.github.io/solace-agent-mesh/docs/documentation/components/projects"}
                    className="mb-4 sm:mr-6"
                />
                {projects.length > 0 || searchQuery ? <SearchInput value={searchQuery} onChange={onSearchChange} className="mb-4" testid="projectSearchInput" /> : null}

                {/* Projects Grid */}
                {isLoading ? (
                    <EmptyState variant="loading" title="Loading projects..." />
                ) : projects.length === 0 && searchQuery ? (
                    <EmptyState variant="notFound" title="No Projects Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => onSearchChange("") }]} />
                ) : projects.length === 0 ? (
                    <EmptyState variant="noImage" title="No Projects Found" subtitle={<ProjectsDescriptionTwoParagraphs />} buttons={[{ text: "Create New Project", variant: "default", onClick: () => onCreateNew() }]} />
                ) : (
                    <div className="flex-1 overflow-y-auto">
                        <div className="flex flex-wrap gap-6">
                            <div className="w-full sm:w-auto">
                                <CreateProjectCard onClick={onCreateNew} />
                            </div>
                            {projects.map(project => (
                                <div key={project.id} className="w-full sm:w-auto">
                                    <ProjectCard project={project} onClick={() => onProjectClick(project)} onDelete={onDelete} onExport={onExport} onShare={onShare} onTogglePin={onTogglePin} isPinToggling={isPinToggling} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
