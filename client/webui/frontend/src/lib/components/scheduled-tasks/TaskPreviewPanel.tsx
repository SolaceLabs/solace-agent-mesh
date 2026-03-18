import React, { useRef, useEffect, useState } from "react";
import { Badge, CardTitle, Label } from "@/lib/components/ui";
import { Calendar, Clock, User, MessageSquare, CheckCircle2 } from "lucide-react";

interface TaskConfig {
    name: string;
    description: string;
    scheduleType: "cron" | "interval" | "one_time";
    scheduleExpression: string;
    targetAgentName: string;
    taskMessage: string;
    timezone: string;
    enabled: boolean;
}

interface TaskPreviewPanelProps {
    config: TaskConfig;
    highlightedFields: string[];
    isReadyToSave: boolean;
}

export const TaskPreviewPanel: React.FC<TaskPreviewPanelProps> = ({ config, highlightedFields, isReadyToSave }) => {
    // Only show content when we have actual task data, not just defaults
    const hasContent = config.name && config.name.trim().length > 0;

    // Track if we've ever had content before to distinguish initial generation from updates
    // hadContentOnPreviousRenderRef tracks if content existed BEFORE the current update
    const hadContentOnPreviousRenderRef = useRef(false);
    const [showBadges, setShowBadges] = useState(false);

    useEffect(() => {
        // Only show badges if we had content BEFORE this update
        // This means the first generation won't show badges, but subsequent updates will
        if (highlightedFields.length > 0 && hadContentOnPreviousRenderRef.current) {
            setShowBadges(true);
        } else if (highlightedFields.length === 0) {
            // Reset when no fields are highlighted
            setShowBadges(false);
        }

        // Update the "had content before" flag for the NEXT render
        // This runs AFTER we check, so the first time content appears,
        // hadContentOnPreviousRenderRef will still be false
        hadContentOnPreviousRenderRef.current = !!hasContent;
    }, [highlightedFields, hasContent]);

    const isFieldHighlighted = (field: string) => highlightedFields.includes(field) && showBadges;

    const getScheduleTypeLabel = (type: string) => {
        switch (type) {
            case "cron":
                return "Recurring (Cron)";
            case "interval":
                return "Interval";
            case "one_time":
                return "One Time";
            default:
                return type;
        }
    };

    const formatScheduleExpression = (type: string, expression: string) => {
        if (!expression) return "Not set";

        if (type === "cron") {
            // Try to make cron more readable
            const parts = expression.split(" ");
            if (parts.length === 5) {
                const [minute, hour, day, month, weekday] = parts;
                if (minute === "0" && hour !== "*" && day === "*" && month === "*" && weekday === "*") {
                    return `Daily at ${hour}:00`;
                }
                if (minute === "0" && hour === "*" && day === "*" && month === "*" && weekday === "*") {
                    return "Every hour";
                }
            }
        }

        return expression;
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b px-6 py-4">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Task Preview</CardTitle>
                    {isReadyToSave && (
                        <Badge variant="default" className="bg-green-500">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Ready to Save
                        </Badge>
                    )}
                </div>
            </div>

            {/* Preview Content */}
            <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
                {/* Task Name */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Label className="text-muted-foreground text-sm font-medium">Task Name</Label>
                        {isFieldHighlighted("name") && (
                            <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded p-3 text-sm">{config.name || <span className="text-muted-foreground italic">No task name yet</span>}</div>
                </div>

                {/* Description */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Label className="text-muted-foreground text-sm font-medium">Description</Label>
                        {isFieldHighlighted("description") && (
                            <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded p-3 text-sm">{config.description || <span className="text-muted-foreground italic">No description yet</span>}</div>
                </div>

                {/* Schedule */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Calendar className="text-muted-foreground h-4 w-4" />
                        <label className="text-muted-foreground text-sm font-medium">Schedule</label>
                        {(isFieldHighlighted("scheduleType") || isFieldHighlighted("scheduleExpression")) && (
                            <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="bg-card space-y-2 rounded-lg border p-3">
                        <div className="flex items-center justify-between">
                            <span className="text-muted-foreground text-xs">Type</span>
                            <span className="text-sm font-medium">{getScheduleTypeLabel(config.scheduleType)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-muted-foreground text-xs">Expression</span>
                            <span className="font-mono text-sm">{formatScheduleExpression(config.scheduleType, config.scheduleExpression)}</span>
                        </div>
                        {config.timezone && (
                            <div className="flex items-center justify-between">
                                <span className="text-muted-foreground text-xs">Timezone</span>
                                <span className="text-sm">{config.timezone}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Target Agent */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <User className="text-muted-foreground h-4 w-4" />
                        <label className="text-muted-foreground text-sm font-medium">Target Agent</label>
                        {isFieldHighlighted("targetAgentName") && (
                            <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="bg-card rounded-lg border p-3">
                        <p className="text-sm font-medium">{config.targetAgentName || <span className="text-muted-foreground italic">Not set</span>}</p>
                    </div>
                </div>

                {/* Task Message */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <MessageSquare className="text-muted-foreground h-4 w-4" />
                        <label className="text-muted-foreground text-sm font-medium">Task Message</label>
                        {isFieldHighlighted("taskMessage") && (
                            <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="bg-card rounded-lg border p-3">
                        <p className="text-sm whitespace-pre-wrap">{config.taskMessage || <span className="text-muted-foreground italic">Not set</span>}</p>
                    </div>
                </div>

                {/* Status */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Clock className="text-muted-foreground h-4 w-4" />
                        <label className="text-muted-foreground text-sm font-medium">Status</label>
                    </div>
                    <div className="bg-card rounded-lg border p-3">
                        <div className="flex items-center gap-2">
                            <div className={`h-2 w-2 rounded-full ${config.enabled ? "bg-green-500" : "bg-gray-400"}`} />
                            <span className="text-sm">{config.enabled ? "Enabled" : "Disabled"}</span>
                        </div>
                    </div>
                </div>

                {/* Help Text */}
                {!isReadyToSave && (
                    <div className="bg-muted/50 rounded-lg p-4">
                        <p className="text-muted-foreground text-sm">Continue chatting with the AI to refine your task configuration. When all required fields are set, you'll be able to save the task.</p>
                    </div>
                )}
            </div>
        </div>
    );
};
