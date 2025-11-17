import React, { useState, useEffect } from 'react';
import {
    Button,
    Input,
    Textarea,
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
    Label,
} from '@/lib/components/ui';
import { Sparkles, Loader2, Pencil } from 'lucide-react';
import { Header } from '@/lib/components/header';
import { MessageBanner } from '@/lib/components/common';
import { TaskBuilderChat } from './TaskBuilderChat';
import { TaskPreviewPanel } from './TaskPreviewPanel';
import { ScheduleBuilder } from './ScheduleBuilder';
import { useAgentCards } from '@/lib/hooks/useAgentCards';
import type { CreateScheduledTaskRequest, ScheduledTask } from '@/lib/types/scheduled-tasks';

// Common timezones for the dropdown
const COMMON_TIMEZONES = [
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Toronto',
    'America/Vancouver',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Asia/Singapore',
    'Asia/Dubai',
    'Australia/Sydney',
    'Pacific/Auckland',
    'UTC',
];

interface TaskConfig {
    name: string;
    description: string;
    schedule_type: 'cron' | 'interval' | 'one_time';
    schedule_expression: string;
    target_agent_name: string;
    task_message: string;
    timezone: string;
    enabled: boolean;
}

interface TaskTemplateBuilderProps {
    onBack: () => void;
    onSuccess?: (taskId?: string) => void;
    initialMessage?: string | null;
    initialMode?: 'manual' | 'ai-assisted';
    editingTask?: ScheduledTask | null;
    isEditing?: boolean;
}

export const TaskTemplateBuilder: React.FC<TaskTemplateBuilderProps> = ({
    onBack,
    onSuccess,
    initialMessage,
    initialMode = 'ai-assisted',
    editingTask,
    isEditing = false,
}) => {
    const [builderMode, setBuilderMode] = useState<'manual' | 'ai-assisted'>(initialMode);
    const [isReadyToSave, setIsReadyToSave] = useState(false);
    const [highlightedFields, setHighlightedFields] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
    const { agents } = useAgentCards();
    
    const [config, setConfig] = useState<TaskConfig>({
        name: '',
        description: '',
        schedule_type: 'cron',
        schedule_expression: '0 9 * * *',
        target_agent_name: 'OrchestratorAgent',
        task_message: '',
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
        enabled: true,
    });

    // Pre-populate config when editing
    useEffect(() => {
        if (editingTask && isEditing) {
            setConfig({
                name: editingTask.name,
                description: editingTask.description || '',
                schedule_type: editingTask.schedule_type,
                schedule_expression: editingTask.schedule_expression,
                target_agent_name: editingTask.target_agent_name,
                task_message: editingTask.task_message?.[0]?.text || '',
                timezone: editingTask.timezone,
                enabled: editingTask.enabled,
            });
        }
    }, [editingTask, isEditing]);

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
        console.log('TaskTemplateBuilder: Received config updates:', updates);
        
        // Convert updates to TaskConfig format
        const taskUpdates: Partial<TaskConfig> = {};
        
        if (updates.name) taskUpdates.name = String(updates.name);
        if (updates.description) taskUpdates.description = String(updates.description);
        if (updates.schedule_type) taskUpdates.schedule_type = updates.schedule_type as 'cron' | 'interval' | 'one_time';
        if (updates.schedule_expression) taskUpdates.schedule_expression = String(updates.schedule_expression);
        if (updates.target_agent_name) taskUpdates.target_agent_name = String(updates.target_agent_name);
        if (updates.task_message) taskUpdates.task_message = String(updates.task_message);
        if (updates.timezone) taskUpdates.timezone = String(updates.timezone);
        
        updateConfig(taskUpdates);
    };

    const validateConfig = (): boolean => {
        const errors: Record<string, string> = {};
        
        if (!config.name.trim()) {
            errors.name = 'Task name is required';
        }
        
        if (!config.schedule_expression.trim()) {
            errors.schedule_expression = 'Schedule expression is required';
        }
        
        if (!config.target_agent_name.trim()) {
            errors.target_agent_name = 'Target agent is required';
        }
        
        if (!config.task_message.trim()) {
            errors.task_message = 'Task message is required';
        }
        
        setValidationErrors(errors);
        return Object.keys(errors).length === 0;
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
                schedule_type: config.schedule_type,
                schedule_expression: config.schedule_expression,
                timezone: config.timezone,
                target_agent_name: config.target_agent_name,
                task_message: [{ type: 'text', text: config.task_message }],
                enabled: config.enabled,
                timeout_seconds: editingTask?.timeout_seconds || 3600,
            };
            
            const url = isEditing && editingTask
                ? `/api/v1/scheduled-tasks/${editingTask.id}`
                : '/api/v1/scheduled-tasks/';
            
            const method = isEditing ? 'PATCH' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(taskData),
            });
            
            if (response.ok) {
                const task = await response.json();
                if (onSuccess) {
                    onSuccess(task.id);
                }
            } else {
                const error = await response.json();
                console.error(`Failed to ${isEditing ? 'update' : 'create'} task:`, error);
                setValidationErrors({ general: error.detail || `Failed to ${isEditing ? 'update' : 'create'} task` });
            }
        } catch (error) {
            console.error(`Error ${isEditing ? 'updating' : 'creating'} task:`, error);
            setValidationErrors({ general: `An error occurred while ${isEditing ? 'updating' : 'creating'} the task` });
        } finally {
            setIsLoading(false);
        }
    };

    const handleSwitchToManual = () => {
        setBuilderMode('manual');
        setHighlightedFields([]);
    };

    const handleSwitchToAI = () => {
        setBuilderMode('ai-assisted');
        setHighlightedFields([]);
    };

    const hasValidationErrors = Object.keys(validationErrors).length > 0;
    const validationErrorMessages = Object.values(validationErrors).filter(Boolean);

    return (
        <div className="flex h-full flex-col">
            {/* Header with breadcrumbs */}
            <Header
                title={isEditing ? "Edit Scheduled Task" : "Create Scheduled Task"}
                breadcrumbs={[
                    { label: "Scheduled Tasks", onClick: onBack },
                    { label: isEditing ? "Edit Task" : "Create Task" }
                ]}
                buttons={
                    builderMode === 'ai-assisted' ? [
                        <Button
                            key="edit-manually"
                            onClick={handleSwitchToManual}
                            variant="ghost"
                            size="sm"
                        >
                            <Pencil className="h-3 w-3 mr-1" />
                            Edit Manually
                        </Button>
                    ] : [
                        <Button
                            key="build-with-ai"
                            onClick={handleSwitchToAI}
                            variant="ghost"
                            size="sm"
                        >
                            <Sparkles className="h-3 w-3 mr-1" />
                            {isEditing ? 'Edit with AI' : 'Build with AI'}
                        </Button>
                    ]
                }
            />

            {/* Error Banner */}
            {hasValidationErrors && (
                <div className="px-8 py-3">
                    <MessageBanner
                        variant="error"
                        message={`Please fix the following errors: ${validationErrorMessages.join(', ')}`}
                    />
                </div>
            )}

            {/* Content area with left and right panels */}
            <div className="flex flex-1 min-h-0">
                {/* Left Panel - AI Chat (keep mounted but hidden to preserve chat history) */}
                <div className={`w-[40%] overflow-hidden border-r ${builderMode === 'manual' ? 'hidden' : ''}`}>
                    <TaskBuilderChat
                        onConfigUpdate={handleConfigUpdate}
                        currentConfig={config}
                        onReadyToSave={setIsReadyToSave}
                        initialMessage={initialMessage}
                        availableAgents={agents}
                    />
                </div>
                
                {/* Right Panel - Task Preview (only in AI mode) */}
                {builderMode === 'ai-assisted' && (
                    <div className="w-[60%] overflow-hidden bg-muted/30">
                        <TaskPreviewPanel
                            config={config}
                            highlightedFields={highlightedFields}
                            isReadyToSave={isReadyToSave}
                        />
                    </div>
                )}
                
                {/* Manual Mode - Full Width Form */}
                {builderMode === 'manual' && (
                    <div className="flex-1 overflow-y-auto px-8 py-6">
                        <div className="max-w-4xl mx-auto space-y-6">
                            {/* Basic Information */}
                            <div className="space-y-4">
                                <h3 className="text-base font-semibold">Basic Information</h3>
                                
                                <div className="space-y-2">
                                    <Label htmlFor="task-name">Task Name <span className="text-[var(--color-primary-wMain)]">*</span></Label>
                                    <Input
                                        id="task-name"
                                        placeholder="e.g., Daily Report Generation"
                                        value={config.name}
                                        onChange={(e) => updateConfig({ name: e.target.value })}
                                        className={validationErrors.name ? 'border-red-500' : ''}
                                    />
                                    {validationErrors.name && (
                                        <p className="text-sm text-red-600">{validationErrors.name}</p>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="task-description">Description</Label>
                                    <Input
                                        id="task-description"
                                        placeholder="e.g., Generates a daily summary report"
                                        value={config.description}
                                        onChange={(e) => updateConfig({ description: e.target.value })}
                                    />
                                </div>
                            </div>

                            {/* Schedule Configuration */}
                            <div className="space-y-4">
                                <h3 className="text-base font-semibold">Schedule</h3>
                                
                                <div className="space-y-2">
                                    <Label htmlFor="schedule-type">Schedule Type</Label>
                                    <Select
                                        value={config.schedule_type}
                                        onValueChange={(value) => updateConfig({ schedule_type: value as 'cron' | 'interval' | 'one_time' })}
                                    >
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
                                {config.schedule_type === 'cron' && (
                                    <ScheduleBuilder
                                        value={config.schedule_expression}
                                        onChange={(cron) => updateConfig({ schedule_expression: cron })}
                                    />
                                )}

                                {/* Interval Input */}
                                {config.schedule_type === 'interval' && (
                                    <div className="space-y-2">
                                        <Label htmlFor="schedule-expression">
                                            Interval <span className="text-[var(--color-primary-wMain)]">*</span>
                                        </Label>
                                        <Input
                                            id="schedule-expression"
                                            placeholder="30m, 1h, 2h, etc."
                                            value={config.schedule_expression}
                                            onChange={(e) => updateConfig({ schedule_expression: e.target.value })}
                                            className={`max-w-xs ${validationErrors.schedule_expression ? 'border-red-500' : ''}`}
                                        />
                                        {validationErrors.schedule_expression && (
                                            <p className="text-sm text-red-600">{validationErrors.schedule_expression}</p>
                                        )}
                                        <p className="text-xs text-muted-foreground">
                                            Format: 30m, 1h, 2h, etc.
                                        </p>
                                    </div>
                                )}

                                {/* One Time Date Picker */}
                                {config.schedule_type === 'one_time' && (
                                    <div className="space-y-2">
                                        <Label htmlFor="schedule-expression">
                                            Date & Time <span className="text-[var(--color-primary-wMain)]">*</span>
                                        </Label>
                                        <Input
                                            id="schedule-expression"
                                            placeholder="2025-12-25T09:00:00"
                                            value={config.schedule_expression}
                                            onChange={(e) => updateConfig({ schedule_expression: e.target.value })}
                                            className={`max-w-md ${validationErrors.schedule_expression ? 'border-red-500' : ''}`}
                                        />
                                        {validationErrors.schedule_expression && (
                                            <p className="text-sm text-red-600">{validationErrors.schedule_expression}</p>
                                        )}
                                        <p className="text-xs text-muted-foreground">
                                            ISO 8601 format: YYYY-MM-DDTHH:MM:SS
                                        </p>
                                    </div>
                                )}

                                <div className="space-y-2">
                                    <Label htmlFor="timezone">Timezone</Label>
                                    <Select
                                        value={config.timezone}
                                        onValueChange={(value) => updateConfig({ timezone: value })}
                                    >
                                        <SelectTrigger className="max-w-md">
                                            <SelectValue placeholder="Select timezone" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {COMMON_TIMEZONES.map((tz) => (
                                                <SelectItem key={tz} value={tz}>
                                                    {tz}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <p className="text-xs text-muted-foreground">
                                        Your local timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}
                                    </p>
                                </div>
                            </div>

                            {/* Task Configuration */}
                            <div className="space-y-4">
                                <h3 className="text-base font-semibold">Task Configuration</h3>
                                
                                <div className="space-y-2">
                                    <Label htmlFor="target-agent">Target Agent <span className="text-[var(--color-primary-wMain)]">*</span></Label>
                                    <Select
                                        value={config.target_agent_name}
                                        onValueChange={(value) => updateConfig({ target_agent_name: value })}
                                    >
                                        <SelectTrigger className={validationErrors.target_agent_name ? 'border-red-500' : ''}>
                                            <SelectValue placeholder="Select an agent" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {agents.map((agent) => (
                                                <SelectItem key={agent.name} value={agent.name}>
                                                    {agent.name}
                                                    {agent.description && (
                                                        <span className="text-xs text-muted-foreground ml-2">
                                                            - {agent.description}
                                                        </span>
                                                    )}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    {validationErrors.target_agent_name && (
                                        <p className="text-sm text-red-600">{validationErrors.target_agent_name}</p>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="task-message">Task Message <span className="text-[var(--color-primary-wMain)]">*</span></Label>
                                    <Textarea
                                        id="task-message"
                                        placeholder="Enter the message to send to the agent..."
                                        value={config.task_message}
                                        onChange={(e) => updateConfig({ task_message: e.target.value })}
                                        rows={6}
                                        className={validationErrors.task_message ? 'border-red-500' : ''}
                                    />
                                    {validationErrors.task_message && (
                                        <p className="text-sm text-red-600">{validationErrors.task_message}</p>
                                    )}
                                </div>

                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        id="enabled"
                                        checked={config.enabled}
                                        onChange={(e) => updateConfig({ enabled: e.target.checked })}
                                    />
                                    <Label htmlFor="enabled" className="cursor-pointer">
                                        Enable task immediately
                                    </Label>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer Actions */}
            <div className="flex justify-end gap-2 p-4 border-t">
                <Button variant="ghost" onClick={onBack} disabled={isLoading}>
                    {isEditing ? 'Discard Changes' : 'Cancel'}
                </Button>
                <Button
                    onClick={handleSave}
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            {isEditing ? 'Saving...' : 'Creating...'}
                        </>
                    ) : (
                        isEditing ? 'Save' : 'Create'
                    )}
                </Button>
            </div>
        </div>
    );
};