import React from "react";
import { Trash2 } from "lucide-react";

import type { Project } from "@/lib/types/projects";
import { Button } from "@/lib/components/ui/button";

interface ProjectListItemProps {
    project: Project;
    isSelected: boolean;
    onClick: () => void;
    onDelete?: (project: Project) => void;
}

export const ProjectListItem: React.FC<ProjectListItemProps> = ({ project, isSelected, onClick, onDelete }) => {
    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        onDelete?.(project);
    };

    return (
        <div
            className={`
                group cursor-pointer px-4 py-2 transition-colors
                hover:bg-accent/50
                ${isSelected ? "bg-accent" : ""}
            `}
            onClick={onClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onClick();
                }
            }}
        >
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1" onClick={onClick}>
                    <h3 className="font-semibold text-foreground truncate mb-1" title={project.name}>
                        {project.name}
                    </h3>
                    {project.description && (
                        <p className="text-sm text-muted-foreground line-clamp-2" title={project.description}>
                            {project.description}
                        </p>
                    )}
                </div>
                {onDelete && (
                    <div className="flex items-center opacity-0 transition-opacity group-hover:opacity-100">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleDelete}
                            title="Delete project"
                            className="h-8 w-8 p-0"
                        >
                            <Trash2 size={16} />
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};
