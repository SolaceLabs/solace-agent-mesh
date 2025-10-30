import React, { useState } from "react";
import { FolderOpen } from "lucide-react";

import { Spinner } from "@/lib/components/ui/spinner";
import type { Project } from "@/lib/types/projects";
import { ProjectListItem } from "./ProjectListItem";
import { DeleteProjectDialog } from "./DeleteProjectDialog";

interface ProjectListSidebarProps {
    projects: Project[];
    selectedProject: Project | null;
    isLoading: boolean;
    error: string | null;
    onProjectSelect: (project: Project) => void;
    onCreateNew: () => void;
    onProjectDelete?: (projectId: string) => Promise<void>;
}

export const ProjectListSidebar: React.FC<ProjectListSidebarProps> = ({
    projects,
    selectedProject,
    isLoading,
    error,
    onProjectSelect,
    onProjectDelete,
}) => {
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const handleDeleteClick = (project: Project) => {
        setProjectToDelete(project);
        setIsDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!projectToDelete || !onProjectDelete) return;

        setIsDeleting(true);
        try {
            await onProjectDelete(projectToDelete.id);
            setIsDeleteDialogOpen(false);
            setProjectToDelete(null);
        } catch (error) {
            console.error("Failed to delete project:", error);
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="flex h-full flex-col bg-background border-r">
            {/* Project List */}
            <div className="flex-1 overflow-y-auto py-6 px-6">
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
                        <p className="text-sm text-muted-foreground">
                            No projects yet
                        </p>
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
                                onDelete={onProjectDelete ? handleDeleteClick : undefined}
                            />
                        ))}
                    </div>
                )}
            </div>

            <DeleteProjectDialog
                isOpen={isDeleteDialogOpen}
                onClose={() => {
                    setIsDeleteDialogOpen(false);
                    setProjectToDelete(null);
                }}
                onConfirm={handleDeleteConfirm}
                project={projectToDelete}
                isDeleting={isDeleting}
            />
        </div>
    );
};
