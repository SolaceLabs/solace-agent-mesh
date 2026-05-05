import React, { useState, useEffect } from "react";
import { Button, Input, Textarea, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Label, DatePicker } from "@/lib/components/ui";
import { Sparkles, Loader2, Pencil } from "lucide-react";
import { Header } from "@/lib/components/header";
import { MessageBanner } from "@/lib/components/common";
import { TaskBuilderChat } from "./TaskBuilderChat";
import { TaskPreviewPanel } from "./TaskPreviewPanel";
import { ScheduleBuilder, SchedulePreviewBox, TimeOfDayPicker } from "./ScheduleBuilder";
import { describeScheduleExpression } from "./utils";
import { useAgentCards, useNavigationBlocker } from "@/lib/hooks";
import { useCreateScheduledTask, useUpdateScheduledTask, scheduledTaskService } from "@/lib/api/scheduled-tasks";
import { cn } from "@/lib/utils";
import type { CreateScheduledTaskRequest, ScheduledTask, TargetType } from "@/lib/types/scheduled-tasks";

// Common timezones for the dropdown
const COMMON_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Toronto",
    "America/Vancouver",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Singapore",
    "Asia/Dubai",
    "Australia/Sydney",
    "Pacific/Auckland",
    "UTC",
];

// Interval schedule supports integer values suffixed by a unit: s | m | h | d.
// Backend enforces a minimum of 60 seconds (see parse_interval_to_seconds).
type IntervalUnit = "s" | "m" | "h" | "d";
const INTERVAL_UNITS: Array<{ value: IntervalUnit; label: string; seconds: number }> = [
    { value: "s", label: "Seconds", seconds: 1 },
    { value: "m", label: "Minutes", seconds: 60 },
    { value: "h", label: "Hours", seconds: 3600 },
    { value: "d", label: "Days", seconds: 86400 },
];
const MIN_INTERVAL_SECONDS = 60;
// 1 year. Mirror the backend's MAXIMUM_INTERVAL_SECONDS — APScheduler's
// IntervalTrigger overflows the underlying C int well past this bound, and
// no realistic recurring task needs more than yearly cadence.
const MAX_INTERVAL_SECONDS = 365 * 86400;

function parseInterval(expr: string): { value: number; unit: IntervalUnit } {
    const match = /^(\d+)([smhd])$/i.exec(expr.trim());
    if (!match) return { value: 30, unit: "m" };
    return { value: parseInt(match[1], 10), unit: match[2].toLowerCase() as IntervalUnit };
}

function intervalToSeconds(value: number, unit: IntervalUnit): number {
    return value * (INTERVAL_UNITS.find(u => u.value === unit)?.seconds ?? 1);
}

// Local-state-driven interval value input. The previous implementation read
// directly from the cron-derived `parsed.value` and rejected empty/invalid
// keystrokes, which trapped the user — they couldn't even delete the digits
// to type a different number. This component lets the field accept any raw
// digits while typing, and only commits back to the parent when the value
// becomes a valid positive integer.
const IntervalValueInput: React.FC<{ value: number; unit: IntervalUnit; onChange: (newValue: number) => void; invalid?: boolean }> = ({ value, unit, onChange, invalid }) => {
    const [draft, setDraft] = useState(Number.isFinite(value) ? String(value) : "");

    // When the parent expression changes (e.g. the AI builder set a new
    // interval, or the user switched units), sync the visible draft.
    useEffect(() => {
        setDraft(Number.isFinite(value) ? String(value) : "");
    }, [value, unit]);

    return (
        <Input
            id="interval-value"
            type="text"
            inputMode="numeric"
            value={draft}
            onChange={e => {
                const next = e.target.value;
                // Allow empty or digits-only while typing — don't reject the keystroke.
                if (next === "" || /^\d+$/.test(next)) {
                    setDraft(next);
                    const n = parseInt(next, 10);
                    if (Number.isFinite(n) && n >= 1) {
                        onChange(n);
                    }
                }
            }}
            onBlur={() => {
                // If the user left the field empty or zero, snap back to the last
                // committed valid value so the cron expression stays well-formed.
                if (!draft || parseInt(draft, 10) < 1) {
                    setDraft(Number.isFinite(value) ? String(value) : "");
                }
            }}
            className={cn("max-w-[7rem]", invalid && "border-(--error-w100)")}
            aria-invalid={invalid}
        />
    );
};

interface TaskConfig {
    name: string;
    description: string;
    scheduleType: "cron" | "interval" | "one_time";
    scheduleExpression: string;
    targetType: TargetType;
    targetAgentName: string;
    taskMessage: string;
    timezone: string;
    enabled: boolean;
}

interface TaskTemplateBuilderProps {
    onBack: () => void;
    onSuccess?: (taskId?: string) => void;
    initialMessage?: string | null;
    initialMode?: "manual" | "ai-assisted";
    editingTask?: ScheduledTask | null;
    isEditing?: boolean;
}

export const TaskTemplateBuilder: React.FC<TaskTemplateBuilderProps> = ({ onBack, onSuccess, initialMessage, initialMode = "ai-assisted", editingTask, isEditing = false }) => {
    const [builderMode, setBuilderMode] = useState<"manual" | "ai-assisted">(initialMode);
    const [isReadyToSave, setIsReadyToSave] = useState(false);
    const [highlightedFields, setHighlightedFields] = useState<string[]>([]);
    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
    // LLM-detected semantic conflict between instructions and schedule. Surfaces
    // as inline error text + red borders on the affected fields. The first save
    // attempt that triggers a conflict aborts and shows the warning; a second
    // save attempt with the same content overrides and proceeds (so the user
    // can dismiss false positives without leaving the form).
    type ConflictState = { reason: string; fields: Array<"instructions" | "schedule">; signature: string } | null;
    const [conflictError, setConflictError] = useState<ConflictState>(null);
    const [isCheckingConflict, setIsCheckingConflict] = useState(false);
    // Tracks which footer button is currently in-flight so only that one shows
    // its spinner. Without this, both Create and Create-and-Activate would
    // show the spinner whenever either was clicked.
    const [pendingAction, setPendingAction] = useState<"create" | "create-activate" | "save" | null>(null);
    const { agents } = useAgentCards();
    const createTaskMutation = useCreateScheduledTask();
    const updateTaskMutation = useUpdateScheduledTask();
    const isLoading = createTaskMutation.isPending || updateTaskMutation.isPending || isCheckingConflict;

    // For unsaved changes detection
    const [initialConfig, setInitialConfig] = useState<TaskConfig | null>(null);
    const { allowNavigation, NavigationBlocker, setBlockingEnabled } = useNavigationBlocker();

    const [config, setConfig] = useState<TaskConfig>({
        name: "",
        description: "",
        scheduleType: "cron",
        scheduleExpression: "",
        targetType: "agent",
        targetAgentName: "OrchestratorAgent",
        taskMessage: "",
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        enabled: true,
    });

    // Remember the last expression the user had for each schedule type so
    // switching cron → interval → cron doesn't wipe their entries.
    const [scheduleExprByType, setScheduleExprByType] = useState<Record<TaskConfig["scheduleType"], string>>({
        cron: "0 9 * * *",
        interval: "30m",
        one_time: "",
    });

    useEffect(() => {
        setScheduleExprByType(prev => (prev[config.scheduleType] === config.scheduleExpression ? prev : { ...prev, [config.scheduleType]: config.scheduleExpression }));
    }, [config.scheduleType, config.scheduleExpression]);

    // Pre-populate config when editing and capture initial state
    useEffect(() => {
        if (editingTask && isEditing) {
            const initialData: TaskConfig = {
                name: editingTask.name,
                description: editingTask.description || "",
                scheduleType: editingTask.scheduleType,
                scheduleExpression: editingTask.scheduleExpression,
                targetType: editingTask.targetType || "agent",
                targetAgentName: editingTask.targetAgentName,
                taskMessage: editingTask.taskMessage?.[0]?.text || "",
                timezone: editingTask.timezone,
                enabled: editingTask.enabled,
            };
            setConfig(initialData);
            setInitialConfig(initialData);
        } else {
            // For new tasks, set empty initial config
            setInitialConfig({
                name: "",
                description: "",
                scheduleType: "cron",
                scheduleExpression: "",
                targetType: "agent",
                targetAgentName: "OrchestratorAgent",
                taskMessage: "",
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
                enabled: true,
            });
        }
    }, [editingTask, isEditing]);

    // Enable/disable navigation blocking based on unsaved changes
    useEffect(() => {
        if (!initialConfig) {
            setBlockingEnabled(false);
            return;
        }

        // Check if current form has any actual content
        const hasContent = !!(config.name?.trim() || config.description?.trim() || config.taskMessage?.trim());

        // If form is empty, no unsaved changes
        if (!hasContent) {
            setBlockingEnabled(false);
            return;
        }

        // Otherwise, check if values differ from initial state
        const hasUnsavedChanges =
            config.name !== initialConfig.name ||
            config.description !== initialConfig.description ||
            config.scheduleType !== initialConfig.scheduleType ||
            config.scheduleExpression !== initialConfig.scheduleExpression ||
            config.targetType !== initialConfig.targetType ||
            config.targetAgentName !== initialConfig.targetAgentName ||
            config.taskMessage !== initialConfig.taskMessage ||
            config.timezone !== initialConfig.timezone ||
            config.enabled !== initialConfig.enabled;

        setBlockingEnabled(hasUnsavedChanges);
    }, [config, initialConfig, setBlockingEnabled]);

    const updateConfig = (updates: Partial<TaskConfig>) => {
        setConfig(prev => ({ ...prev, ...updates }));

        // Track which fields were updated for highlighting
        const changedFields = Object.keys(updates);
        setHighlightedFields(changedFields);

        // Clear validation errors for updated fields
        setValidationErrors(prev => {
            const newErrors = { ...prev };
            changedFields.forEach(field => delete newErrors[field]);
            return newErrors;
        });
    };

    const handleConfigUpdate = (updates: Record<string, unknown>) => {
        // Convert updates to TaskConfig format (handle both snake_case from API and camelCase)
        const taskUpdates: Partial<TaskConfig> = {};

        if (updates.name) taskUpdates.name = String(updates.name);
        if (updates.description) taskUpdates.description = String(updates.description);
        if (updates.scheduleType || updates.schedule_type) taskUpdates.scheduleType = (updates.scheduleType || updates.schedule_type) as "cron" | "interval" | "one_time";
        if (updates.scheduleExpression || updates.schedule_expression) taskUpdates.scheduleExpression = String(updates.scheduleExpression || updates.schedule_expression);
        if (updates.targetType || updates.target_type) taskUpdates.targetType = (updates.targetType || updates.target_type) as TargetType;
        if (updates.targetAgentName || updates.target_agent_name) taskUpdates.targetAgentName = String(updates.targetAgentName || updates.target_agent_name);
        if (updates.taskMessage || updates.task_message) taskUpdates.taskMessage = String(updates.taskMessage || updates.task_message);
        if (updates.timezone) taskUpdates.timezone = String(updates.timezone);

        // Filter to only fields that actually changed from current values
        const changedFields = Object.keys(taskUpdates).filter(key => {
            const oldValue = (config as unknown as Record<string, unknown>)[key];
            const newValue = (taskUpdates as unknown as Record<string, unknown>)[key];

            // Compare values, treating undefined/null/empty string as equivalent
            const normalizedOld = oldValue === undefined || oldValue === null || oldValue === "" ? "" : oldValue;
            const normalizedNew = newValue === undefined || newValue === null || newValue === "" ? "" : newValue;

            return normalizedOld !== normalizedNew;
        });

        setConfig(prev => ({ ...prev, ...taskUpdates }));

        // Only show badges for fields that actually changed
        setHighlightedFields(changedFields);

        // Clear validation errors for updated fields
        setValidationErrors(prev => {
            const newErrors = { ...prev };
            changedFields.forEach(field => delete newErrors[field]);
            return newErrors;
        });
    };

    const validateConfig = (): boolean => {
        const errors: Record<string, string> = {};

        if (!config.name.trim()) {
            errors.name = "Task name is required";
        }

        if (!config.scheduleExpression.trim()) {
            errors.scheduleExpression = "Schedule expression is required";
        } else if (config.scheduleType === "one_time") {
            // Backend enforces strict ISO 8601 (Python's datetime.fromisoformat).
            // `new Date(...)` is too lenient in some browsers and would let
            // garbage like "2026-04-16T15:21:00A" through to the server.
            const iso8601Pattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$/;
            if (!iso8601Pattern.test(config.scheduleExpression.trim())) {
                errors.scheduleExpression = "Invalid date & time — use format YYYY-MM-DDTHH:MM:SS";
            } else {
                const scheduled = new Date(config.scheduleExpression);
                if (isNaN(scheduled.getTime())) {
                    errors.scheduleExpression = "Invalid date & time";
                } else if (scheduled.getTime() <= Date.now()) {
                    errors.scheduleExpression = "Scheduled time must be in the future";
                }
            }
        } else if (config.scheduleType === "interval") {
            const match = /^(\d+)([smhd])$/i.exec(config.scheduleExpression.trim());
            if (!match) {
                errors.scheduleExpression = "Interval must be a positive number followed by s, m, h, or d (e.g. 30m)";
            } else {
                const seconds = intervalToSeconds(parseInt(match[1], 10), match[2].toLowerCase() as IntervalUnit);
                if (seconds < MIN_INTERVAL_SECONDS) {
                    errors.scheduleExpression = `Interval must be at least ${MIN_INTERVAL_SECONDS} seconds`;
                } else if (seconds > MAX_INTERVAL_SECONDS) {
                    errors.scheduleExpression = "Interval must be at most 1 year";
                }
            }
        }

        if (!config.timezone.trim()) {
            errors.timezone = "Timezone is required";
        }

        if (!config.targetAgentName.trim()) {
            errors.targetAgentName = "Target agent is required";
        }

        if (!config.taskMessage.trim()) {
            errors.taskMessage = "Instructions are required";
        }

        setValidationErrors(errors);
        return Object.keys(errors).length === 0;
    };

    const handleClose = (skipCheck = false) => {
        if (skipCheck) {
            allowNavigation(() => {
                setInitialConfig(null);
                onBack();
            });
        } else {
            onBack();
        }
    };

    // Signature used to detect "user has not changed anything since the
    // conflict warning" — second Create click with same data acts as override.
    const conflictSignature = (cfg: TaskConfig) => `${cfg.scheduleType}|${cfg.scheduleExpression}|${cfg.timezone}|${cfg.taskMessage}`;

    // Any edit to the conflict-relevant fields invalidates the prior verdict.
    useEffect(() => {
        if (!conflictError) return;
        if (conflictSignature(config) !== conflictError.signature) {
            setConflictError(null);
        }
    }, [config.scheduleType, config.scheduleExpression, config.timezone, config.taskMessage, conflictError]);

    const handleSave = async (activate?: boolean) => {
        if (!validateConfig()) {
            return;
        }

        const action: "create" | "create-activate" | "save" = isEditing ? "save" : activate ? "create-activate" : "create";
        setPendingAction(action);

        // Conflict-check on first save attempt. If the user clicks Create
        // again with the exact same content, treat that as an explicit override.
        const signature = conflictSignature(config);
        const alreadyWarned = !!conflictError && conflictError.signature === signature;
        if (!alreadyWarned) {
            setIsCheckingConflict(true);
            try {
                const result = await scheduledTaskService.validateTaskConflict({
                    instructions: config.taskMessage,
                    scheduleType: config.scheduleType,
                    scheduleExpression: config.scheduleExpression,
                    timezone: config.timezone,
                    targetAgent: config.targetAgentName,
                });
                if (result.conflict) {
                    setConflictError({
                        reason: result.reason || "Instructions are conflicting with the schedule configuration. Review the task instructions and schedule.",
                        fields: result.affectedFields.length > 0 ? result.affectedFields : ["instructions", "schedule"],
                        signature,
                    });
                    setIsCheckingConflict(false);
                    setPendingAction(null);
                    return;
                }
            } catch {
                // Fail open — don't block the user if validation itself errors.
            }
            setIsCheckingConflict(false);
        }

        const enabled = isEditing ? config.enabled : activate === true;

        try {
            const taskData: CreateScheduledTaskRequest = {
                name: config.name,
                description: config.description,
                scheduleType: config.scheduleType,
                scheduleExpression: config.scheduleExpression,
                timezone: config.timezone,
                targetAgentName: config.targetAgentName,
                targetType: config.targetType,
                taskMessage: [{ type: "text", text: config.taskMessage }],
                enabled,
                timeoutSeconds: editingTask?.timeoutSeconds || 3600,
            };

            let savedTask;
            if (isEditing && editingTask) {
                savedTask = await updateTaskMutation.mutateAsync({ taskId: editingTask.id, updates: taskData });
            } else {
                savedTask = await createTaskMutation.mutateAsync(taskData);
            }

            // Clear unsaved state and close without check
            allowNavigation(() => {
                handleClose(true);
                if (onSuccess) {
                    onSuccess(savedTask.id);
                }
            });
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : `An error occurred while ${isEditing ? "updating" : "creating"} the task`;
            setValidationErrors({ general: errorMsg });
        } finally {
            setPendingAction(null);
        }
    };

    const handleSwitchToManual = () => {
        setBuilderMode("manual");
        setHighlightedFields([]);
    };

    const handleSwitchToAI = () => {
        setBuilderMode("ai-assisted");
        setHighlightedFields([]);
    };

    const hasValidationErrors = Object.keys(validationErrors).length > 0;
    const validationErrorMessages = Object.values(validationErrors).filter(Boolean);

    return (
        <>
            <div className="flex h-full flex-col">
                {/* Header with breadcrumbs */}
                <Header
                    title={isEditing ? "Edit Scheduled Task" : "Create Scheduled Task"}
                    breadcrumbs={[{ label: "Scheduled Tasks", onClick: () => handleClose() }, { label: isEditing ? "Edit Task" : "Create Task" }]}
                    buttons={
                        builderMode === "ai-assisted"
                            ? [
                                  <Button key="edit-manually" onClick={handleSwitchToManual} variant="ghost" size="sm">
                                      <Pencil className="mr-1 h-3 w-3" />
                                      Edit Manually
                                  </Button>,
                              ]
                            : [
                                  <Button key="build-with-ai" onClick={handleSwitchToAI} variant="ghost" size="sm">
                                      <Sparkles className="mr-1 h-3 w-3" />
                                      {isEditing ? "Edit with AI" : "Build with AI"}
                                  </Button>,
                              ]
                    }
                />

                {/* Error Banner — lists exact errors; each source field is highlighted separately */}
                {hasValidationErrors && (
                    <div className="px-8 py-3">
                        <MessageBanner
                            variant="error"
                            message={
                                validationErrorMessages.length === 1 ? (
                                    <span>{validationErrorMessages[0]}</span>
                                ) : (
                                    <div>
                                        <p className="font-semibold">Please fix the following:</p>
                                        <ul className="mt-1 ml-5 list-disc">
                                            {validationErrorMessages.map((msg, i) => (
                                                <li key={i}>{msg}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )
                            }
                        />
                    </div>
                )}

                {/* Content area with left and right panels */}
                <div className="flex min-h-0 flex-1">
                    {/* Left Panel - AI Chat (keep mounted but hidden to preserve chat history) */}
                    <div className={cn("w-[40%] overflow-hidden border-r", builderMode === "manual" && "hidden")}>
                        <TaskBuilderChat onConfigUpdate={handleConfigUpdate} currentConfig={config} onReadyToSave={setIsReadyToSave} initialMessage={initialMessage} availableAgents={agents} isEditing={isEditing} />
                    </div>

                    {/* Right Panel - Task Preview (only in AI mode) */}
                    {builderMode === "ai-assisted" && (
                        <div className="w-[60%] overflow-hidden">
                            <TaskPreviewPanel config={config} highlightedFields={highlightedFields} isReadyToSave={isReadyToSave} />
                        </div>
                    )}

                    {/* Manual Mode - Full Width Form */}
                    {builderMode === "manual" && (
                        <div className="flex-1 overflow-y-auto px-8 py-6">
                            <div className="mx-auto max-w-4xl space-y-6">
                                {/* Basic Information */}
                                <div className="space-y-4">
                                    <h3 className="text-base font-semibold">Basic Information</h3>

                                    <div className="space-y-2">
                                        <Label htmlFor="task-name">
                                            Task Name <span className="text-(--primary-wMain)">*</span>
                                        </Label>
                                        <Input id="task-name" placeholder="e.g., Daily Report Generation" value={config.name} onChange={e => updateConfig({ name: e.target.value })} className={validationErrors.name ? "border-(--error-w100)" : ""} />
                                        {validationErrors.name && <p className="text-sm text-(--error-wMain)">{validationErrors.name}</p>}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="task-description">Description</Label>
                                        <Textarea id="task-description" placeholder="e.g., Generates a daily summary report" value={config.description} onChange={e => updateConfig({ description: e.target.value })} rows={3} />
                                    </div>
                                </div>

                                {/* Schedule Configuration */}
                                <div className="space-y-4">
                                    <h3 className="text-base font-semibold">Schedule</h3>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="schedule-type">
                                                Schedule Type <span className="text-(--primary-wMain)">*</span>
                                            </Label>
                                            <Select
                                                value={config.scheduleType}
                                                onValueChange={value => {
                                                    const newType = value as TaskConfig["scheduleType"];
                                                    updateConfig({ scheduleType: newType, scheduleExpression: scheduleExprByType[newType] });
                                                }}
                                            >
                                                <SelectTrigger className={cn("w-full", conflictError?.fields.includes("schedule") && "border-(--error-w100)")}>
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="cron">Recurring Schedule</SelectItem>
                                                    <SelectItem value="interval">Interval</SelectItem>
                                                    <SelectItem value="one_time">One Time</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            {conflictError?.fields.includes("schedule") && <p className="text-sm text-(--error-wMain)">{conflictError.reason}</p>}
                                        </div>

                                        <div className="space-y-2">
                                            <Label htmlFor="timezone">
                                                Timezone <span className="text-(--primary-wMain)">*</span>
                                            </Label>
                                            <Select value={config.timezone} onValueChange={value => updateConfig({ timezone: value })}>
                                                <SelectTrigger className="w-full">
                                                    <SelectValue placeholder="Select timezone" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {COMMON_TIMEZONES.map(tz => (
                                                        <SelectItem key={tz} value={tz}>
                                                            {tz}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>

                                    {/* Use ScheduleBuilder for cron */}
                                    {config.scheduleType === "cron" && <ScheduleBuilder value={config.scheduleExpression} onChange={cron => updateConfig({ scheduleExpression: cron })} />}

                                    {/* Interval Input */}
                                    {config.scheduleType === "interval" &&
                                        (() => {
                                            const parsed = parseInterval(config.scheduleExpression);
                                            const invalid = !!validationErrors.scheduleExpression;
                                            return (
                                                <>
                                                    <div className="space-y-2">
                                                        <Label htmlFor="interval-value">
                                                            Interval <span className="text-(--primary-wMain)">*</span>
                                                        </Label>
                                                        <div className="flex items-center gap-2">
                                                            <IntervalValueInput value={parsed.value} unit={parsed.unit} onChange={n => updateConfig({ scheduleExpression: `${n}${parsed.unit}` })} invalid={invalid} />
                                                            <Select value={parsed.unit} onValueChange={val => updateConfig({ scheduleExpression: `${parsed.value}${val}` })}>
                                                                <SelectTrigger className={cn("max-w-[10rem]", invalid && "border-(--error-w100)")} aria-invalid={invalid}>
                                                                    <SelectValue />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {INTERVAL_UNITS.map(u => (
                                                                        <SelectItem key={u.value} value={u.value}>
                                                                            {u.label}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                        {invalid && <p className="text-sm text-(--error-wMain)">{validationErrors.scheduleExpression}</p>}
                                                        <p className="text-xs text-(--secondary-text-wMain)">Interval must be between {MIN_INTERVAL_SECONDS} seconds and 1 year.</p>
                                                    </div>
                                                </>
                                            );
                                        })()}

                                    {/* One Time Date & Time Picker */}
                                    {config.scheduleType === "one_time" && (
                                        <>
                                            <div className="space-y-2">
                                                <Label>
                                                    Date & Time <span className="text-(--primary-wMain)">*</span>
                                                </Label>
                                                <div className="flex items-center gap-2">
                                                    <DatePicker
                                                        value={config.scheduleExpression.split("T")[0] || ""}
                                                        onChange={date => {
                                                            const time = config.scheduleExpression.split("T")[1] || "09:00:00";
                                                            updateConfig({ scheduleExpression: date ? `${date}T${time}` : "" });
                                                        }}
                                                        min={new Date().toISOString().split("T")[0]}
                                                        invalid={!!validationErrors.scheduleExpression}
                                                    />
                                                    <TimeOfDayPicker
                                                        value={(config.scheduleExpression.split("T")[1] || "").substring(0, 5)}
                                                        onChange={time => {
                                                            const date = config.scheduleExpression.split("T")[0] || "";
                                                            updateConfig({ scheduleExpression: date ? `${date}T${time}:00` : "" });
                                                        }}
                                                        invalid={!!validationErrors.scheduleExpression}
                                                    />
                                                </div>
                                                {validationErrors.scheduleExpression && <p className="text-sm text-(--error-wMain)">{validationErrors.scheduleExpression}</p>}
                                            </div>
                                            {!validationErrors.scheduleExpression && config.scheduleExpression && <SchedulePreviewBox description={describeScheduleExpression("one_time", config.scheduleExpression)} />}
                                        </>
                                    )}
                                </div>

                                {/* Task Configuration */}
                                <div className="space-y-4">
                                    <h3 className="text-base font-semibold">Task Configuration</h3>

                                    <div className="space-y-2">
                                        <Label>
                                            Output <span className="text-(--primary-wMain)">*</span>
                                        </Label>
                                        <p className="text-sm">Chat</p>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="target-type">
                                                Target <span className="text-(--primary-wMain)">*</span>
                                            </Label>
                                            <Select value={config.targetType} onValueChange={value => updateConfig({ targetType: value as TargetType, targetAgentName: "" })}>
                                                <SelectTrigger className="w-full">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="agent">Agent</SelectItem>
                                                    <SelectItem value="workflow">Workflow</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="space-y-2">
                                            <Label htmlFor="target-agent">
                                                {config.targetType === "workflow" ? "Workflow Type" : "Agent Type"} <span className="text-(--primary-wMain)">*</span>
                                            </Label>
                                            <Select value={config.targetAgentName} onValueChange={value => updateConfig({ targetAgentName: value })}>
                                                <SelectTrigger className={cn("w-full", validationErrors.targetAgentName && "border-(--error-w100)")}>
                                                    <SelectValue placeholder={`Select a ${config.targetType === "workflow" ? "workflow" : "agent"}`} />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {agents
                                                        .filter(agent => (config.targetType === "workflow" ? agent.isWorkflow : !agent.isWorkflow))
                                                        .map(agent => (
                                                            <SelectItem key={agent.name} value={agent.name}>
                                                                {agent.displayName || agent.name}
                                                            </SelectItem>
                                                        ))}
                                                </SelectContent>
                                            </Select>
                                            {validationErrors.targetAgentName && <p className="text-sm text-(--error-wMain)">{validationErrors.targetAgentName}</p>}
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="task-message">
                                            Instructions <span className="text-(--primary-wMain)">*</span>
                                        </Label>
                                        <p className="text-sm text-(--secondary-text-wMain)">Enter the task instructions for the agent to execute on the configured schedule.</p>
                                        <Textarea
                                            id="task-message"
                                            placeholder="Enter the message to send to the agent..."
                                            value={config.taskMessage}
                                            onChange={e => updateConfig({ taskMessage: e.target.value })}
                                            rows={6}
                                            className={validationErrors.taskMessage || conflictError?.fields.includes("instructions") ? "border-(--error-w100)" : ""}
                                        />
                                        <p className="text-xs text-(--secondary-text-wMain)">Ensure the instructions match the schedule and task configuration.</p>
                                        {validationErrors.taskMessage && <p className="text-sm text-(--error-wMain)">{validationErrors.taskMessage}</p>}
                                        {conflictError?.fields.includes("instructions") && (
                                            <p className="text-sm text-(--error-wMain)">
                                                {conflictError.reason} <span className="text-xs text-(--secondary-text-wMain)">— click Create again to save anyway.</span>
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
                <NavigationBlocker />
                {/* Footer Actions */}
                <div className="flex justify-end gap-2 border-t p-4">
                    <Button variant="ghost" onClick={() => handleClose()} disabled={isLoading}>
                        {isEditing ? "Discard Changes" : "Cancel"}
                    </Button>
                    {isEditing ? (
                        <Button onClick={() => handleSave()} disabled={isLoading}>
                            {pendingAction === "save" ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                "Save"
                            )}
                        </Button>
                    ) : (
                        <>
                            <Button variant="outline" onClick={() => handleSave(false)} disabled={isLoading}>
                                {pendingAction === "create" ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Creating...
                                    </>
                                ) : (
                                    "Create"
                                )}
                            </Button>
                            <Button onClick={() => handleSave(true)} disabled={isLoading}>
                                {pendingAction === "create-activate" ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Creating...
                                    </>
                                ) : (
                                    "Create and Activate"
                                )}
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </>
    );
};
