import React from "react";
import { Calendar, User, FileText } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, Badge } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { formatTimestamp } from "@/lib/utils/format";

interface ProjectCardProps {
    project: Project;
    onClick?: () => void;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick }) => {
    const handleClick = () => {
        onClick?.();
    };

    return (
        <Card
            className={`
                h-[196px] w-full sm:w-[380px] flex-shrink-0 cursor-pointer transition-all duration-200
                hover:shadow-lg hover:scale-[1.02] bg-card border overflow-hidden
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
                    {project.artifactCount !== undefined && project.artifactCount !== null && (
                        <Badge variant="secondary" className="flex items-center gap-1 shrink-0">
                            <FileText className="h-3 w-3" />
                            <span>{project.artifactCount}</span>
                        </Badge>
                    )}
                </div>
            </CardHeader>
            
            <CardContent className="pt-0">
                <div className="space-y-3">
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
                    
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
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
                </div>
            </CardContent>
        </Card>
    );
};
