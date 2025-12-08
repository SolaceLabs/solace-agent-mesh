import React, { useState, useEffect } from "react";
import { Button, Input, Textarea, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Label } from "@/lib/components/ui";
import { Sparkles, Loader2, Pencil } from "lucide-react";
import { Header } from "@/lib/components/header";
import { MessageBanner } from "@/lib/components/common";
import { TaskBuilderChat } from "./TaskBuilderChat";
import { TaskPreviewPanel } from "./TaskPreviewPanel";
import { ScheduleBuilder } from "./ScheduleBuilder";
import { useAgentCards, useNavigationBlocker } from "@/lib/hooks";
import type { CreateScheduledTaskRequest, ScheduledTask } from "@/lib/types/scheduled-tasks";

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
    const [isLoading, setIsLoading] = useState(false);
    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
    const { agents } = useAgentCards();

    // For unsaved changes detection
    const [initialConfig, setInitialConfig] = useState<TaskConfig | null>(null);
    const { allowNavigation, NavigationBlocker, setBlockingEnabled } = useNavigationBlocker();

    const [config, setConfig] = useState<TaskConfig>({
        name: "",
        description: "",
        scheduleType: "cron",
        scheduleExpression: "0 9 * * *",
        targetAgentName: "OrchestratorAgent",
        taskMessage: "",
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        enabled: true,
    });

    // Pre-populate config when editing and capture initial state
    useEffect(() => {
        if (editingTask && isEditing) {
            const initialData: TaskConfig = {
                name: editingTask.name,
                description: editingTask.description || "",
                scheduleType: editingTask.scheduleType,
                scheduleExpression: editingTask.scheduleExpression,
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
                scheduleExpression: "0 9 * * *",
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
        console.log("TaskTemplateBuilder: Received config updates:", updates);

        // Convert updates to TaskConfig format (handle both snake_case from API and camelCase)
        const taskUpdates: Partial<TaskConfig> = {};

        if (updates.name) taskUpdates.name = String(updates.name);
        if (updates.description) taskUpdates.description = String(updates.description);
        if (updates.scheduleType || updates.schedule_type) taskUpdates.scheduleType = (updates.scheduleType || updates.schedule_type) as "cron" | "interval" | "one_time";
        if (updates.scheduleExpression || updates.schedule_expression) taskUpdates.scheduleExpression = String(updates.scheduleExpression || updates.schedule_expression);
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
        }

        if (!config.targetAgentName.trim()) {
            errors.targetAgentName = "Target agent is required";
        }

        if (!config.taskMessage.trim()) {
            errors.taskMessage = "Task message is required";
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

    const handleSave = async () => {
        if (!validateConfig()) {
            return;
        }

        setIsLoading(true);

        try {
            const taskData: CreateScheduledTaskRequest = {
                name: config.name,
                description: config.description,
                scheduleType: config.scheduleType,
                scheduleExpression: config.scheduleExpression,
                timezone: config.timezone,
                targetAgentName: config.targetAgentName,
                taskMessage: [{ type: "text", text: config.taskMessage }],
                enabled: config.enabled,
                timeoutSeconds: editingTask?.timeoutSeconds || 3600,
            };

            const url = isEditing && editingTask ? `/api/v1/scheduled-tasks/${editingTask.id}` : "/api/v1/scheduled-tasks/";

            const method = isEditing ? "PATCH" : "POST";

            // Transform to API format (snake_case)
            const apiData = {
                name: taskData.name,
                description: taskData.description,
                schedule_type: taskData.scheduleType,
                schedule_expression: taskData.scheduleExpression,
                timezone: taskData.timezone,
                target_agent_name: taskData.targetAgentName,
                task_message: taskData.taskMessage,
                enabled: taskData.enabled,
                timeout_seconds: taskData.timeoutSeconds,
            };

            const response = await fetch(url, {
                method,
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "include",
                body: JSON.stringify(apiData),
            });

            if (response.ok) {
                const task = await response.json();
                // Clear unsaved state and close without check
                allowNavigation(() => {
                    handleClose(true);
                    if (onSuccess) {
                        onSuccess(task.id);
                    }
                });
            } else {
                const error = await response.json();
                console.error(`Failed to ${isEditing ? "update" : "create"} task:`, error);
                setValidationErrors({ general: error.detail || `Failed to ${isEditing ? "update" : "create"} task` });
            }
        } catch (error) {
            console.error(`Error ${isEditing ? "updating" : "creating"} task:`, error);
            setValidationErrors({ general: `An error occurred while ${isEditing ? "updating" : "creating"} the task` });
        } finally {
            setIsLoading(false);
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

                {/* Error Banner */}
                {hasValidationErrors && (
                    <div className="px-8 py-3">
                        <MessageBanner variant="error" message={`Please fix the following errors: ${validationErrorMessages.join(", ")}`} />
                    </div>
                )}

                {/* Content area with left and right panels */}
                <div className="flex min-h-0 flex-1">
                    {/* Left Panel - AI Chat (keep mounted but hidden to preserve chat history) */}
                    <div className={`w-[40%] overflow-hidden border-r ${builderMode === "manual" ? "hidden" : ""}`}>
                        <TaskBuilderChat onConfigUpdate={handleConfigUpdate} currentConfig={config} onReadyToSave={setIsReadyToSave} initialMessage={initialMessage} availableAgents={agents} />
                    </div>

                    {/* Right Panel - Task Preview (only in AI mode) */}
                    {builderMode === "ai-assisted" && (
                        <div className="bg-muted/30 w-[60%] overflow-hidden">
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
                                            Task Name <span className="text-[var(--color-primary-wMain)]">*</span>
                                        </Label>
                                        <Input id="task-name" placeholder="e.g., Daily Report Generation" value={config.name} onChange={e => updateConfig({ name: e.target.value })} className={validationErrors.name ? "border-red-500" : ""} />
                                        {validationErrors.name && <p className="text-sm text-red-600">{validationErrors.name}</p>}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="task-description">Description</Label>
                                        <Input id="task-description" placeholder="e.g., Generates a daily summary report" value={config.description} onChange={e => updateConfig({ description: e.target.value })} />
                                    </div>
                                </div>

                                {/* Schedule Configuration */}
                                <div className="space-y-4">
                                    <h3 className="text-base font-semibold">Schedule</h3>

                                    <div className="space-y-2">
                                        <Label htmlFor="schedule-type">Schedule Type</Label>
                                        <Select value={config.scheduleType} onValueChange={value => updateConfig({ scheduleType: value as "cron" | "interval" | "one_time" })}>
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="cron">Recurring Schedule</SelectItem>
                                                <SelectItem value="interval">Interval</SelectItem>
                                                <SelectItem value="one_time">One Time</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {/* Use ScheduleBuilder for cron */}
                                    {config.scheduleType === "cron" && <ScheduleBuilder value={config.scheduleExpression} onChange={cron => updateConfig({ scheduleExpression: cron })} />}

                                    {/* Interval Input */}
                                    {config.scheduleType === "interval" && (
                                        <div className="space-y-2">
                                            <Label htmlFor="schedule-expression">
                                                Interval <span className="text-[var(--color-primary-wMain)]">*</span>
                                            </Label>
                                            <Input
                                                id="schedule-expression"
                                                placeholder="30m, 1h, 2h, etc."
                                                value={config.scheduleExpression}
                                                onChange={e => updateConfig({ scheduleExpression: e.target.value })}
                                                className={`max-w-xs ${validationErrors.scheduleExpression ? "border-red-500" : ""}`}
                                            />
                                            {validationErrors.scheduleExpression && <p className="text-sm text-red-600">{validationErrors.scheduleExpression}</p>}
                                            <p className="text-muted-foreground text-xs">Format: 30m, 1h, 2h, etc.</p>
                                        </div>
                                    )}

                                    {/* One Time Date Picker */}
                                    {config.scheduleType === "one_time" && (
                                        <div className="space-y-2">
                                            <Label htmlFor="schedule-expression">
                                                Date & Time <span className="text-[var(--color-primary-wMain)]">*</span>
                                            </Label>
                                            <Input
                                                id="schedule-expression"
                                                placeholder="2025-12-25T09:00:00"
                                                value={config.scheduleExpression}
                                                onChange={e => updateConfig({ scheduleExpression: e.target.value })}
                                                className={`max-w-md ${validationErrors.scheduleExpression ? "border-red-500" : ""}`}
                                            />
                                            {validationErrors.scheduleExpression && <p className="text-sm text-red-600">{validationErrors.scheduleExpression}</p>}
                                            <p className="text-muted-foreground text-xs">ISO 8601 format: YYYY-MM-DDTHH:MM:SS</p>
                                        </div>
                                    )}

                                    <div className="space-y-2">
                                        <Label htmlFor="timezone">Timezone</Label>
                                        <Select value={config.timezone} onValueChange={value => updateConfig({ timezone: value })}>
                                            <SelectTrigger className="max-w-md">
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
                                        <p className="text-muted-foreground text-xs">Your local timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>
                                    </div>
                                </div>

                                {/* Task Configuration */}
                                <div className="space-y-4">
                                    <h3 className="text-base font-semibold">Task Configuration</h3>

                                    <div className="space-y-2">
                                        <Label htmlFor="target-agent">
                                            Target Agent <span className="text-[var(--color-primary-wMain)]">*</span>
                                        </Label>
                                        <Select value={config.targetAgentName} onValueChange={value => updateConfig({ targetAgentName: value })}>
                                            <SelectTrigger className={validationErrors.targetAgentName ? "border-red-500" : ""}>
                                                <SelectValue placeholder="Select an agent" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {agents.map(agent => (
                                                    <SelectItem key={agent.name} value={agent.name}>
                                                        {agent.name}
                                                        {agent.description && <span className="text-muted-foreground ml-2 text-xs">- {agent.description}</span>}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                        {validationErrors.targetAgentName && <p className="text-sm text-red-600">{validationErrors.targetAgentName}</p>}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="task-message">
                                            Task Message <span className="text-[var(--color-primary-wMain)]">*</span>
                                        </Label>
                                        <Textarea
                                            id="task-message"
                                            placeholder="Enter the message to send to the agent..."
                                            value={config.taskMessage}
                                            onChange={e => updateConfig({ taskMessage: e.target.value })}
                                            rows={6}
                                            className={validationErrors.taskMessage ? "border-red-500" : ""}
                                        />
                                        {validationErrors.taskMessage && <p className="text-sm text-red-600">{validationErrors.taskMessage}</p>}
                                    </div>

                                    <div className="flex items-center gap-2">
                                        <input type="checkbox" id="enabled" checked={config.enabled} onChange={e => updateConfig({ enabled: e.target.checked })} />
                                        <Label htmlFor="enabled" className="cursor-pointer">
                                            Enable task immediately
                                        </Label>
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
                    <Button onClick={handleSave} disabled={isLoading}>
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                {isEditing ? "Saving..." : "Creating..."}
                            </>
                        ) : isEditing ? (
                            "Save"
                        ) : (
                            "Create"
                        )}
                    </Button>
                </div>
            </div>
        </>
    );
};
