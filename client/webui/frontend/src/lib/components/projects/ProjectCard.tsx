import React from "react";
import { Calendar, User, FileText, Trash2 } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, Badge, Button } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { formatTimestamp } from "@/lib/utils/format";

interface ProjectCardProps {
    project: Project;
    onClick?: () => void;
    onDelete?: (project: Project) => void;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick, onDelete }) => {
    const handleClick = () => {
        onClick?.();
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        onDelete?.(project);
    };

    return (
        <Card
            className={`
                group h-[196px] w-full sm:w-[380px] flex-shrink-0 cursor-pointer transition-all duration-200
                hover:shadow-lg bg-card border overflow-hidden flex flex-col
                ${onClick ? 'hover:bg-accent/50' : ''}
            `}
            onClick={handleClick}
            role={onClick ? "button" : undefined}
            tabIndex={onClick ? 0 : undefined}
        >
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                        <CardTitle className="line-clamp-2 text-lg font-semibold text-foreground leading-tight" title={project.name}>
                            {project.name}
                        </CardTitle>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                        {project.artifactCount !== undefined && project.artifactCount !== null && (
                            <Badge variant="secondary" className="flex items-center gap-1 h-6">
                                <FileText className="h-3.5 w-3.5" />
                                <span>{project.artifactCount}</span>
                            </Badge>
                        )}
                        {onDelete && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleDelete}
                                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive hover:bg-destructive/10"
                                title="Delete project"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                        )}
                    </div>
                </div>
            </CardHeader>
            
            <CardContent className="pt-0 flex-1 flex flex-col">
                <div className="flex-1">
                    {project.description ? (
                        <CardDescription
                            className="line-clamp-2 text-sm text-muted-foreground"
                            title={project.description}
                        >
                            {project.description}
                        </CardDescription>
                    ) : (
                        <CardDescription className="text-sm text-muted-foreground italic">
                            No description provided
                        </CardDescription>
                    )}
                </div>
                
                <div className="flex items-center justify-between text-xs text-muted-foreground mt-3">
                    <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span>Created {formatTimestamp(project.createdAt)}</span>
                    </div>
                    
                    <div className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        <span className="truncate max-w-[80px]" title={project.userId}>
                            {project.userId}
                        </span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
