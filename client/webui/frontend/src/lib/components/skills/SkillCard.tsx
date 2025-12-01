import React, { useState } from "react";
import { Lightbulb, Tag, MoreHorizontal, Users, CheckCircle, XCircle, MessageSquare } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import type { SkillSummary } from "@/lib/types/skills";

interface SkillCardProps {
    skill: SkillSummary;
    isSelected: boolean;
    onSkillClick: () => void;
    onUseInChat?: (skill: SkillSummary) => void;
}

export const SkillCard: React.FC<SkillCardProps> = ({ skill, isSelected, onSkillClick, onUseInChat }) => {
    const [dropdownOpen, setDropdownOpen] = useState(false);

    // Format success rate as percentage
    const successRateDisplay = skill.successRate !== undefined && skill.successRate !== null ? `${Math.round(skill.successRate * 100)}%` : "N/A";

    // Get scope badge color
    const getScopeBadgeClass = (scope: string) => {
        switch (scope) {
            case "global":
                return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
            case "agent":
                return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
            case "user":
                return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
            case "shared":
                return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
            default:
                return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
        }
    };

    // Get type badge color
    const getTypeBadgeClass = (type: string) => {
        switch (type) {
            case "learned":
                return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
            case "authored":
                return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200";
            default:
                return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
        }
    };

    return (
        <GridCard isSelected={isSelected} onClick={onSkillClick}>
            <div className="flex h-full w-full flex-col">
                <div className="flex items-center justify-between px-4">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <Lightbulb className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                        <div className="min-w-0">
                            <h2 className="truncate text-lg font-semibold" title={skill.name}>
                                {skill.name}
                            </h2>
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={e => {
                                        e.stopPropagation();
                                        setDropdownOpen(!dropdownOpen);
                                    }}
                                    tooltip="Actions"
                                    className="cursor-pointer"
                                >
                                    <MoreHorizontal size={16} />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" onClick={e => e.stopPropagation()}>
                                <DropdownMenuItem
                                    onClick={e => {
                                        e.stopPropagation();
                                        setDropdownOpen(false);
                                        if (onUseInChat) {
                                            onUseInChat(skill);
                                        }
                                    }}
                                >
                                    <MessageSquare size={14} className="mr-2" />
                                    Use in Chat
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>
                <div className="flex flex-grow flex-col overflow-hidden px-4">
                    {skill.ownerAgent && (
                        <div className="text-muted-foreground mb-2 flex items-center gap-1 text-xs">
                            <Users size={12} />
                            {skill.ownerAgent}
                        </div>
                    )}
                    <div className="mb-3 line-clamp-2 text-sm leading-5">{skill.description || "No description provided."}</div>
                    <div className="mt-auto">
                        <div className="flex flex-wrap items-center gap-2">
                            {/* Type badge */}
                            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${getTypeBadgeClass(skill.type)}`}>{skill.type === "learned" ? "Learned" : "Authored"}</span>
                            {/* Scope badge */}
                            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${getScopeBadgeClass(skill.scope)}`}>
                                <Tag size={10} />
                                {skill.scope}
                            </span>
                            {/* Success rate */}
                            <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                                {skill.successRate !== undefined && skill.successRate >= 0.7 ? <CheckCircle size={12} className="text-green-500" /> : skill.successRate !== undefined ? <XCircle size={12} className="text-red-500" /> : null}
                                {successRateDisplay}
                            </span>
                            {/* Usage count */}
                            {skill.usageCount > 0 && <span className="text-muted-foreground text-xs">{skill.usageCount} uses</span>}
                        </div>
                    </div>
                </div>
            </div>
        </GridCard>
    );
};
