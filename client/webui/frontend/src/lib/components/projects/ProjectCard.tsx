import React, { useState, useRef, useEffect } from "react";
import { FileText, FolderOpen, MoreHorizontal, Download, Trash2, Share2, Eye, UserIcon } from "lucide-react";

import { GridCard, GRID_CARD_DIMENSIONS } from "@/lib/components/common";
import { CardContent, CardDescription, CardHeader, CardTitle, Button, Popover, PopoverContent, PopoverTrigger, Menu, Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import type { MenuAction } from "@/lib/components/ui/menu";
import type { Project } from "@/lib/types/projects";
import { useIsProjectOwner } from "@/lib/hooks";

interface ProjectCardProps {
    project: Project;
    onClick?: () => void;
    onDelete?: (project: Project) => void;
    onExport?: (project: Project) => void;
    onShare?: (project: Project) => void;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick, onDelete, onExport, onShare }) => {
    const [menuOpen, setMenuOpen] = useState(false);
    const [isTruncated, setIsTruncated] = useState(false);
    const titleRef = useRef<HTMLDivElement>(null);
    const isOwner = useIsProjectOwner(project.userId);

    useEffect(() => {
        const element = titleRef.current;
        if (element) {
            setIsTruncated(element.scrollWidth > element.clientWidth);
        }
    }, [project.name]);

    const menuActions: MenuAction[] = [
        ...(isOwner && onShare
            ? [
                  {
                      id: "share",
                      label: "Share Project",
                      icon: <Share2 size={14} />,
                      onClick: () => {
                          setMenuOpen(false);
                          onShare(project);
                      },
                  },
              ]
            : []),
        ...(onExport
            ? [
                  {
                      id: "export",
                      label: "Export Project",
                      icon: <Download size={14} />,
                      onClick: () => {
                          setMenuOpen(false);
                          onExport(project);
                      },
                  },
              ]
            : []),
        {
            id: "delete",
            label: "Delete",
            icon: <Trash2 size={14} />,
            onClick: () => {
                setMenuOpen(false);
                if (onDelete) {
                    onDelete(project);
                }
            },
        },
    ];

    return (
        <GridCard onClick={onClick} className={GRID_CARD_DIMENSIONS.project}>
            <CardHeader className="gap-0">
                <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <FolderOpen className="h-6 w-6 flex-shrink-0 text-(--brand-wMain)" />
                        {isTruncated ? (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <CardTitle ref={titleRef} className="text-(--primary-text-wMain) max-w-[250px] min-w-0 truncate text-lg font-semibold">
                                        {project.name}
                                    </CardTitle>
                                </TooltipTrigger>
                                <TooltipContent side="top">{project.name}</TooltipContent>
                            </Tooltip>
                        ) : (
                            <CardTitle ref={titleRef} className="text-(--primary-text-wMain) max-w-[250px] min-w-0 truncate text-lg font-semibold">
                                {project.name}
                            </CardTitle>
                        )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                        {isOwner && onDelete && (
                            <Popover open={menuOpen} onOpenChange={setMenuOpen}>
                                <PopoverTrigger asChild>
                                    <Button variant="ghost" size="icon" className="h-8 w-8" tooltip="More options" onClick={e => e.stopPropagation()}>
                                        <MoreHorizontal className="h-4 w-4" />
                                    </Button>
                                </PopoverTrigger>
                                <PopoverContent align="start" side="bottom" className="w-48 p-1" sideOffset={0} onClick={e => e.stopPropagation()}>
                                    <Menu actions={menuActions} />
                                </PopoverContent>
                            </Popover>
                        )}
                    </div>
                </div>
            </CardHeader>

            <CardContent className="flex flex-1 flex-col justify-between gap-4">
                <div>{project.description ? <CardDescription className="line-clamp-3">{project.description}</CardDescription> : <div />}</div>

                <div className="flex items-center justify-between">
                    <div className="text-(--secondary-text-wMain) max-w-[200px] truncate">{project.userId}</div>
                    <div className="flex items-center gap-4">
                        {project.artifactCount !== undefined && project.artifactCount !== null && (
                            <div className="text-secondary-foreground flex items-center gap-1">
                                <FileText className="h-4 w-4 text-(--color-secondary-wMain)" />
                                <span>
                                    {project.artifactCount} {project.artifactCount === 1 ? "file" : "files"}
                                </span>
                            </div>
                        )}
                        {onShare && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <span className="text-secondary-foreground cursor-default">{isOwner ? <UserIcon className="h-6 w-6" /> : <Eye className="h-6 w-6" />}</span>
                                </TooltipTrigger>
                                <TooltipContent side="top">{isOwner ? "You are the owner of this project" : "You are a viewer of this project"}</TooltipContent>
                            </Tooltip>
                        )}
                    </div>
                </div>
            </CardContent>
        </GridCard>
    );
};
