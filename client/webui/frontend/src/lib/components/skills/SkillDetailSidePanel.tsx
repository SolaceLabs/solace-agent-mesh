import React from "react";
import { X, Lightbulb, Tag, Calendar, User, Users, CheckCircle, XCircle, Zap, ListOrdered, GitBranch, Download, FileText } from "lucide-react";
import type { Skill } from "@/lib/types/skills";
import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { MarkdownHTMLConverter } from "@/lib/components/common/MarkdownHTMLConverter";

interface SkillDetailSidePanelProps {
    skill: Skill | null;
    onClose: () => void;
    onUseInChat?: (skill: Skill) => void;
    onExport?: (skill: Skill) => void;
}

export const SkillDetailSidePanel: React.FC<SkillDetailSidePanelProps> = ({ skill, onClose, onUseInChat, onExport }) => {
    if (!skill) return null;

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

    const handleUseInChat = () => {
        if (onUseInChat) {
            onUseInChat(skill);
        }
    };

    const handleExport = () => {
        if (onExport) {
            onExport(skill);
        }
    };

    // Format date
    const formatDate = (dateStr: string) => {
        if (!dateStr) return "Unknown";
        try {
            return new Date(dateStr).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
            });
        } catch {
            return dateStr;
        }
    };

    return (
        <div className="bg-background flex h-full w-full flex-col border-l">
            {/* Header */}
            <div className="border-b p-4">
                <div className="mb-2 flex items-center justify-between">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <Lightbulb className="text-muted-foreground h-5 w-5 flex-shrink-0" />
                        <Tooltip delayDuration={300}>
                            <TooltipTrigger asChild>
                                <h2 className="cursor-default truncate text-lg font-semibold">{skill.name}</h2>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">
                                <p>{skill.name}</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                    <div className="ml-2 flex flex-shrink-0 items-center gap-1">
                        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0" tooltip="Close">
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    {/* Type badge */}
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getTypeBadgeClass(skill.type)}`}>{skill.type === "learned" ? "Learned" : "Authored"}</span>
                    {/* Scope badge */}
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getScopeBadgeClass(skill.scope)}`}>
                        <Tag size={12} />
                        {skill.scope}
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
                {/* Description - with background */}
                <div className="bg-muted/50 space-y-4 rounded p-4">
                    {/* Description */}
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Description</h3>
                        <div className="text-sm leading-relaxed">{skill.description || "No description provided."}</div>
                    </div>

                    {/* Owner Agent */}
                    {skill.ownerAgent && (
                        <div>
                            <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Owner Agent</h3>
                            <div className="flex items-center gap-2 text-sm">
                                <Users size={14} />
                                {skill.ownerAgent}
                            </div>
                        </div>
                    )}
                </div>

                {/* Skill Content (Markdown) */}
                {skill.markdownContent && (
                    <div>
                        <h3 className="text-muted-foreground mb-3 flex items-center gap-2 text-xs font-semibold">
                            <FileText size={14} />
                            Skill Content
                        </h3>
                        <div className="bg-muted/30 rounded p-4">
                            <MarkdownHTMLConverter className="prose prose-sm dark:prose-invert max-w-none">{skill.markdownContent}</MarkdownHTMLConverter>
                        </div>
                    </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2">
                    {onUseInChat && (
                        <Button onClick={handleUseInChat} className="flex-1">
                            <Zap className="h-4 w-4" />
                            Use in Chat
                        </Button>
                    )}
                    {onExport && (
                        <Button onClick={handleExport} variant="outline" className="flex-1">
                            <Download className="h-4 w-4" />
                            Export
                        </Button>
                    )}
                </div>

                {/* Statistics */}
                <div>
                    <h3 className="text-muted-foreground mb-3 text-xs font-semibold">Statistics</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-muted/30 rounded p-3">
                            <div className="text-muted-foreground mb-1 text-xs">Success Rate</div>
                            <div className="flex items-center gap-2 text-lg font-semibold">
                                {skill.successRate !== undefined && skill.successRate >= 0.7 ? <CheckCircle size={16} className="text-green-500" /> : skill.successRate !== undefined ? <XCircle size={16} className="text-red-500" /> : null}
                                {successRateDisplay}
                            </div>
                        </div>
                        <div className="bg-muted/30 rounded p-3">
                            <div className="text-muted-foreground mb-1 text-xs">Usage Count</div>
                            <div className="text-lg font-semibold">{skill.usageCount}</div>
                        </div>
                        <div className="bg-muted/30 rounded p-3">
                            <div className="text-muted-foreground mb-1 text-xs">Successes</div>
                            <div className="text-lg font-semibold text-green-600">{skill.successCount}</div>
                        </div>
                        <div className="bg-muted/30 rounded p-3">
                            <div className="text-muted-foreground mb-1 text-xs">Failures</div>
                            <div className="text-lg font-semibold text-red-600">{skill.failureCount}</div>
                        </div>
                    </div>
                </div>

                {/* Steps */}
                {skill.steps && skill.steps.length > 0 && (
                    <div>
                        <h3 className="text-muted-foreground mb-3 flex items-center gap-2 text-xs font-semibold">
                            <ListOrdered size={14} />
                            Steps ({skill.steps.length})
                        </h3>
                        <div className="space-y-2">
                            {skill.steps.map((step, index) => (
                                <div key={index} className="bg-muted/30 rounded p-3">
                                    <div className="mb-1 flex items-center gap-2">
                                        <span className="bg-primary/20 text-primary flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium">{step.stepNumber || index + 1}</span>
                                        {step.toolName && <span className="text-muted-foreground font-mono text-xs">{step.toolName}</span>}
                                    </div>
                                    <div className="text-sm">{step.description || step.action || "No description"}</div>
                                    {step.agentName && <div className="text-muted-foreground mt-1 text-xs">Agent: {step.agentName}</div>}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Agent Chain */}
                {skill.agentChain && skill.agentChain.length > 0 && (
                    <div>
                        <h3 className="text-muted-foreground mb-3 flex items-center gap-2 text-xs font-semibold">
                            <GitBranch size={14} />
                            Agent Chain ({skill.agentChain.length})
                        </h3>
                        <div className="space-y-2">
                            {skill.agentChain.map((node, index) => (
                                <div key={index} className="bg-muted/30 rounded p-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200">{node.order}</span>
                                            <span className="text-sm font-medium">{node.agentName}</span>
                                        </div>
                                        {node.role && <span className="text-muted-foreground text-xs">{node.role}</span>}
                                    </div>
                                    {node.toolsUsed && node.toolsUsed.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {node.toolsUsed.map((tool, toolIndex) => (
                                                <span key={toolIndex} className="bg-muted rounded px-1.5 py-0.5 font-mono text-xs">
                                                    {tool}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Tags */}
                {skill.tags && skill.tags.length > 0 && (
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Tags</h3>
                        <div className="flex flex-wrap gap-2">
                            {skill.tags.map((tag, index) => (
                                <span key={index} className="bg-primary/10 text-primary inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium">
                                    <Tag size={10} />
                                    {tag}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Metadata - Sticky at bottom */}
            <div className="bg-background space-y-2 border-t p-4">
                {skill.ownerUserId && (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                        <User size={12} />
                        <span>Created by: {skill.ownerUserId}</span>
                    </div>
                )}
                {skill.createdAt && (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                        <Calendar size={12} />
                        <span>Created: {formatDate(skill.createdAt)}</span>
                    </div>
                )}
                {skill.updatedAt && (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                        <Calendar size={12} />
                        <span>Updated: {formatDate(skill.updatedAt)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};
