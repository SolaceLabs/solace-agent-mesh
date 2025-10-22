import React from "react";
import { Calendar } from "lucide-react";

import type { Project } from "@/lib/types/projects";
import { formatTimestamp } from "@/lib/utils/format";

interface ProjectListItemProps {
    project: Project;
    isSelected: boolean;
    onClick: () => void;
}

export const ProjectListItem: React.FC<ProjectListItemProps> = ({ project, isSelected, onClick }) => {
    return (
        <div
            className={`
                cursor-pointer border-b px-4 py-3 transition-colors
                hover:bg-accent/50
                ${isSelected ? "bg-accent border-l-4 border-l-primary" : "border-l-4 border-l-transparent"}
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
                <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-foreground truncate mb-1" title={project.name}>
                        {project.name}
                    </h3>
                    {project.description && (
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-2" title={project.description}>
                            {project.description}
                        </p>
                    )}
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        <span>{formatTimestamp(project.updatedAt || project.createdAt)}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};
