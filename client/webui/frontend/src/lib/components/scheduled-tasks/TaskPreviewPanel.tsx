import React, { useRef, useEffect, useState } from "react";
import { Badge, CardTitle, Label } from "@/lib/components/ui";
import { Calendar, Clock, User, MessageSquare, CheckCircle2 } from "lucide-react";
import { describeScheduleExpression } from "./utils";

interface TaskConfig {
    name: string;
    description: string;
    scheduleType: "cron" | "interval" | "one_time";
    scheduleExpression: string;
    targetType: "agent" | "workflow";
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

    // Show the schedule in plain English when we can translate it; keep the raw
    // expression available as a tooltip so power users can still verify it.
    const friendlyExpression = describeScheduleExpression(config.scheduleType, config.scheduleExpression);
    const showRawAlongside = config.scheduleType === "cron" && config.scheduleExpression && friendlyExpression !== config.scheduleExpression;

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b px-6 py-4">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Task Preview</CardTitle>
                    {isReadyToSave && (
                        <Badge variant="default" className="bg-green-500">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Ready to Create
                        </Badge>
                    )}
                </div>
            </div>

            {/* Preview Content */}
            <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
                {/* Task Name */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Label className="text-sm font-medium text-(--secondary-text-wMain)">Task Name</Label>
                        {isFieldHighlighted("name") && (
                            <Badge variant="default" className="bg-(--primary-wMain) text-xs text-(--primary-text-w10)">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded p-3 text-sm">{config.name || <span className="text-(--secondary-text-wMain) italic">No task name yet</span>}</div>
                </div>

                {/* Description */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Label className="text-sm font-medium text-(--secondary-text-wMain)">Description</Label>
                        {isFieldHighlighted("description") && (
                            <Badge variant="default" className="bg-(--primary-wMain) text-xs text-(--primary-text-w10)">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded p-3 text-sm">{config.description || <span className="text-(--secondary-text-wMain) italic">No description yet</span>}</div>
                </div>

                {/* Schedule */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-(--secondary-text-wMain)" />
                        <label className="text-sm font-medium text-(--secondary-text-wMain)">Schedule</label>
                        {(isFieldHighlighted("scheduleType") || isFieldHighlighted("scheduleExpression")) && (
                            <Badge variant="default" className="bg-(--primary-wMain) text-xs text-(--primary-text-w10)">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="space-y-2 rounded-lg border bg-(--background-w10) p-3">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-(--secondary-text-wMain)">Type</span>
                            <span className="text-sm font-medium">{getScheduleTypeLabel(config.scheduleType)}</span>
                        </div>
                        <div className="flex items-start justify-between gap-2">
                            <span className="text-xs text-(--secondary-text-wMain)">Expression</span>
                            <div className="flex flex-col items-end text-right">
                                <span className="text-sm" title={showRawAlongside ? config.scheduleExpression : undefined}>
                                    {friendlyExpression}
                                </span>
                                {showRawAlongside && <span className="font-mono text-xs text-(--secondary-text-wMain)">{config.scheduleExpression}</span>}
                            </div>
                        </div>
                        {config.timezone && (
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-(--secondary-text-wMain)">Timezone</span>
                                <span className="text-sm">{config.timezone}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Target Agent/Workflow */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-(--secondary-text-wMain)" />
                        <label className="text-sm font-medium text-(--secondary-text-wMain)">Target {config.targetType === "workflow" ? "Workflow" : "Agent"}</label>
                        {(isFieldHighlighted("targetAgentName") || isFieldHighlighted("targetType")) && (
                            <Badge variant="default" className="bg-(--primary-wMain) text-xs text-(--primary-text-w10)">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded-lg border bg-(--background-w10) p-3">
                        <p className="text-sm font-medium">{config.targetAgentName || <span className="text-(--secondary-text-wMain) italic">Not set</span>}</p>
                    </div>
                </div>

                {/* Task Message */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-(--secondary-text-wMain)" />
                        <label className="text-sm font-medium text-(--secondary-text-wMain)">Task Message</label>
                        {isFieldHighlighted("taskMessage") && (
                            <Badge variant="default" className="bg-(--primary-wMain) text-xs text-(--primary-text-w10)">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded-lg border bg-(--background-w10) p-3">
                        <p className="text-sm whitespace-pre-wrap">{config.taskMessage || <span className="text-(--secondary-text-wMain) italic">Not set</span>}</p>
                    </div>
                </div>

                {/* Activation Setting */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-(--secondary-text-wMain)" />
                        <label className="text-sm font-medium text-(--secondary-text-wMain)">Activation</label>
                    </div>
                    <div className="rounded-lg border bg-(--background-w10) p-3">
                        <div className="flex items-center gap-2">
                            <div className={`h-2 w-2 rounded-full ${config.enabled ? "bg-(--success-wMain)" : "bg-(--secondary-text-wMain)"}`} />
                            <span className="text-sm">{config.enabled ? "Enable immediately on create" : "Create as disabled (paused)"}</span>
                        </div>
                    </div>
                </div>

                {/* Help Text */}
                {!isReadyToSave && (
                    <div className="rounded-lg bg-(--secondary-w20) p-4">
                        <p className="text-sm text-(--secondary-text-wMain)">Continue chatting with the AI to refine your task configuration. When all required fields are set, you'll be able to create the task.</p>
                    </div>
                )}
            </div>
        </div>
    );
};
