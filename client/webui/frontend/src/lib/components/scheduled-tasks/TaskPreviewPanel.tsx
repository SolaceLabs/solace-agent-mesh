import React, { useEffect, useRef, useState } from "react";
import { Badge, CardTitle, Label } from "@/lib/components/ui";
import { CalendarDays } from "lucide-react";
import { describeScheduleExpression } from "./utils";
import { useAgentCards } from "@/lib/hooks";

const INTERVAL_UNIT_LABELS: Record<string, string> = {
    s: "Seconds",
    m: "Minutes",
    h: "Hours",
    d: "Days",
};

function parseInterval(expr: string): { value: string; unit: string } | null {
    const match = /^(\d+)([smhd])$/i.exec(expr.trim());
    if (!match) return null;
    return { value: match[1], unit: match[2].toLowerCase() };
}

function getScheduleTypeLabel(type: string) {
    switch (type) {
        case "cron":
            return "Recurring Schedule";
        case "interval":
            return "Interval";
        case "one_time":
            return "One Time";
        default:
            return type;
    }
}

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

const UpdatedBadge: React.FC = () => (
    <Badge variant="default" className="bg-(--primary-wMain) text-xs text-(--primary-text-w10)">
        Updated
    </Badge>
);

// `indented` renders the value inside a tinted, padded block — used for fields
// that would be a text Input/Textarea in manual mode (Task Name, Description,
// Task Message, Cron Expression, etc). Without `indented`, the value is plain
// text aligned with the label — used for fields that would be a Select.
const FieldRow: React.FC<{ label: string; value?: string; emptyLabel?: string; updated?: boolean; mono?: boolean; multiline?: boolean; indented?: boolean }> = ({ label, value, emptyLabel, updated, mono, multiline, indented }) => {
    const isEmpty = !value || !value.trim();
    const valueClasses = indented ? `rounded-md px-3 py-2 text-sm ${multiline ? "min-h-[120px] whitespace-pre-wrap" : ""} ${mono ? "font-mono" : ""}` : `text-sm ${mono ? "font-mono" : ""} ${multiline ? "min-h-[120px] whitespace-pre-wrap" : ""}`;
    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2">
                <Label className="text-sm font-medium text-(--secondary-text-wMain)">{label}</Label>
                {updated && <UpdatedBadge />}
            </div>
            <div className={valueClasses}>{isEmpty ? <span className="text-(--secondary-text-wMain) italic">{emptyLabel || `No ${label.toLowerCase()} yet`}</span> : value}</div>
        </div>
    );
};

export const TaskPreviewPanel: React.FC<TaskPreviewPanelProps> = ({ config, highlightedFields, isReadyToSave }) => {
    // Only show "Updated" badges after the first generation — don't flash them
    // for every field on the very first AI response.
    const hasContent = !!config.name?.trim();
    const hadContentOnPreviousRenderRef = useRef(false);
    const [showBadges, setShowBadges] = useState(false);

    useEffect(() => {
        if (highlightedFields.length > 0 && hadContentOnPreviousRenderRef.current) {
            setShowBadges(true);
        } else if (highlightedFields.length === 0) {
            setShowBadges(false);
        }
        hadContentOnPreviousRenderRef.current = hasContent;
    }, [highlightedFields, hasContent]);

    const isFieldHighlighted = (field: string) => highlightedFields.includes(field) && showBadges;

    const { agentNameMap } = useAgentCards();
    const targetAgentDisplay = config.targetAgentName ? agentNameMap[config.targetAgentName] || config.targetAgentName : "";

    const friendlyExpression = describeScheduleExpression(config.scheduleType, config.scheduleExpression);
    const showFriendlyPreview = !!config.scheduleExpression && friendlyExpression !== config.scheduleExpression && config.scheduleType !== "interval";

    const interval = config.scheduleType === "interval" ? parseInterval(config.scheduleExpression) : null;
    const oneTimeDate = config.scheduleType === "one_time" ? config.scheduleExpression.split("T")[0] || "" : "";
    const oneTimeTime = config.scheduleType === "one_time" ? (config.scheduleExpression.split("T")[1] || "").substring(0, 5) : "";

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-(--secondary-w10)">
                        <CalendarDays className="h-4 w-4 text-(--secondary-text-wMain)" />
                    </div>
                    <h3 className="text-sm font-semibold">Preview</h3>
                </div>
            </div>

            {/* Read-only summary — same minimal "label + plain padded text" style
                used by the prompt builder's TemplatePreviewPanel so the AI builders
                feel consistent and nothing implies editability. */}
            <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
                <div>
                    <CardTitle className="mb-4 text-base">Basic Information</CardTitle>
                    <div className="space-y-4">
                        <FieldRow label="Task Name" value={config.name} updated={isFieldHighlighted("name")} indented />
                        <FieldRow label="Description" value={config.description} updated={isFieldHighlighted("description")} indented />
                    </div>
                </div>

                <div>
                    <CardTitle className="mb-4 text-base">Schedule</CardTitle>
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
                            <FieldRow label="Schedule Type" value={getScheduleTypeLabel(config.scheduleType)} updated={isFieldHighlighted("scheduleType")} />
                            <FieldRow label="Timezone" value={config.timezone} updated={isFieldHighlighted("timezone")} />
                        </div>

                        {config.scheduleType === "interval" && (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <Label className="text-sm font-medium text-(--secondary-text-wMain)">Interval</Label>
                                    {isFieldHighlighted("scheduleExpression") && <UpdatedBadge />}
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    {interval ? (
                                        <>
                                            <span>{interval.value}</span>
                                            <span className="text-(--secondary-text-wMain)">{INTERVAL_UNIT_LABELS[interval.unit]}</span>
                                        </>
                                    ) : (
                                        <span className="text-(--secondary-text-wMain) italic">No interval yet</span>
                                    )}
                                </div>
                            </div>
                        )}

                        {config.scheduleType === "cron" && <FieldRow label="Cron Expression" value={config.scheduleExpression} updated={isFieldHighlighted("scheduleExpression")} mono indented />}

                        {config.scheduleType === "one_time" && (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <Label className="text-sm font-medium text-(--secondary-text-wMain)">Date &amp; Time</Label>
                                    {isFieldHighlighted("scheduleExpression") && <UpdatedBadge />}
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    {oneTimeDate || oneTimeTime ? (
                                        <>
                                            <span>{oneTimeDate || "—"}</span>
                                            <span>{oneTimeTime || "—"}</span>
                                        </>
                                    ) : (
                                        <span className="text-(--secondary-text-wMain) italic">No date selected yet</span>
                                    )}
                                </div>
                            </div>
                        )}

                        {showFriendlyPreview && (
                            <div className="space-y-2">
                                <Label className="text-sm font-medium text-(--secondary-text-wMain)">Preview</Label>
                                <div className="rounded-md bg-(--background-w10) px-3 py-2 text-sm">{friendlyExpression}</div>
                            </div>
                        )}
                    </div>
                </div>

                <div>
                    <CardTitle className="mb-4 text-base">Task Configuration</CardTitle>
                    <div className="space-y-4">
                        <FieldRow label="Output" value="Chat" />
                        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
                            <FieldRow label="Target" value={config.targetType === "workflow" ? "Workflow" : "Agent"} updated={isFieldHighlighted("targetType")} />
                            <FieldRow label={config.targetType === "workflow" ? "Workflow Type" : "Agent Type"} value={targetAgentDisplay} updated={isFieldHighlighted("targetAgentName")} emptyLabel="Not set" />
                        </div>

                        <FieldRow label="Instructions" value={config.taskMessage} updated={isFieldHighlighted("taskMessage")} multiline indented emptyLabel="No instructions yet" />
                    </div>
                </div>

                {!isReadyToSave && (
                    <div className="rounded-lg bg-(--secondary-w20) p-4">
                        <p className="text-sm text-(--secondary-text-wMain)">Continue chatting with the AI to refine your task configuration. When all required fields are set, you'll be able to create the task.</p>
                    </div>
                )}
            </div>
        </div>
    );
};
