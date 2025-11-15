import React, { useState } from "react";
import { FileText, FolderOpen, MoreHorizontal, Upload, Trash2 } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { CardContent, CardDescription, CardHeader, CardTitle, Badge, Button, Popover, PopoverContent, PopoverTrigger } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { formatTimestamp } from "@/lib/utils/format";

interface ProjectCardProps {
    project: Project;
    onClick?: () => void;
    onDelete?: (project: Project) => void;
    onExport?: (project: Project) => void;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick, onDelete, onExport }) => {
    const [menuOpen, setMenuOpen] = useState(false);
    
    const handleExport = (e: React.MouseEvent) => {
        e.stopPropagation();
        setMenuOpen(false);
        if (onExport) {
            onExport(project);
        }
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        setMenuOpen(false);
        if (onDelete) {
            onDelete(project);
        }
    };

    return (
        <GridCard onClick={onClick}>
            <CardHeader>
                <div className="flex items-start justify-between gap-2">
                    <CardTitle className="flex min-w-0 flex-1 items-center gap-2" title={project.name}>
                        <FolderOpen className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                        <div className="text-foreground text-lg font-semibold">{project.name}</div>
                    </CardTitle>
                    <div className="flex shrink-0 items-center gap-1">
                        {onDelete && (
                            <Popover open={menuOpen} onOpenChange={setMenuOpen}>
                                <PopoverTrigger asChild>
                                    <Button variant="ghost" size="icon" className="h-8 w-8" tooltip="More options" onClick={e => e.stopPropagation()}>
                                        <MoreHorizontal className="h-4 w-4" />
                                    </Button>
                                </PopoverTrigger>
                                <PopoverContent align="start" side="bottom" className="w-48 p-1" sideOffset={0} onClick={e => e.stopPropagation()}>
                                    {onExport && (
                                        <button
                                            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                                            onClick={handleExport}
                                        >
                                            <Upload size={14} />
                                            Export Project
                                        </button>
                                    )}
                                    <button
                                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                                        onClick={handleDelete}
                                    >
                                        <Trash2 size={14} />
                                        Delete
                                    </button>
                                </PopoverContent>
                            </Popover>
                        )}
                    </div>
                </div>
            </CardHeader>

            <CardContent className="flex flex-1 flex-col justify-between">
                <div>
                    {project.description ? (
                        <CardDescription className="line-clamp-3" title={project.description}>
                            {project.description}
                        </CardDescription>
                    ) : (
                        <div />
                    )}
                </div>

                <div className="text-muted-foreground mt-3 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1">
                        Created: {formatTimestamp(project.createdAt)}
                        <div>|</div>
                        <div className="max-w-[80px] truncate" title={project.userId}>
                            {project.userId}
                        </div>
                    </div>
                    <div>
                        {project.artifactCount !== undefined && project.artifactCount !== null && (
                            <Badge variant="secondary" className="flex h-6 items-center gap-1" title={`${project.artifactCount} ${project.artifactCount === 1 ? "file" : "files"}`}>
                                <FileText className="h-3.5 w-3.5" />
                                <span>{project.artifactCount}</span>
                            </Badge>
                        )}
                    </div>
                </div>
            </CardContent>
        </GridCard>
    );
};
