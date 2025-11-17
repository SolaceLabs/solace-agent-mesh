import React, { useRef, useEffect } from 'react';
import { Badge, CardTitle, Label } from '@/lib/components/ui';
import { Calendar, Clock, User, MessageSquare, CheckCircle2 } from 'lucide-react';

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

interface TaskPreviewPanelProps {
    config: TaskConfig;
    highlightedFields: string[];
    isReadyToSave: boolean;
}

export const TaskPreviewPanel: React.FC<TaskPreviewPanelProps> = ({
    config,
    highlightedFields,
    isReadyToSave,
}) => {
    // Only show content when we have actual task data, not just defaults
    const hasContent = config.name && config.name.trim().length > 0;
    
    // Track if we've ever had content before to distinguish initial generation from updates
    const hadContentBeforeRef = useRef(false);
    const previousHighlightedFieldsRef = useRef<string[]>([]);
    
    useEffect(() => {
        // When highlightedFields changes, check if we had content before
        if (highlightedFields.length > 0 && hasContent) {
            if (!hadContentBeforeRef.current) {
                hadContentBeforeRef.current = true;
            }
        }
        previousHighlightedFieldsRef.current = highlightedFields;
    }, [highlightedFields, hasContent]);
    
    const showBadges = hadContentBeforeRef.current && highlightedFields.length > 0;
    
    const isFieldHighlighted = (field: string) => highlightedFields.includes(field) && showBadges;

    const getScheduleTypeLabel = (type: string) => {
        switch (type) {
            case 'cron':
                return 'Recurring (Cron)';
            case 'interval':
                return 'Interval';
            case 'one_time':
                return 'One Time';
            default:
                return type;
        }
    };

    const formatScheduleExpression = (type: string, expression: string) => {
        if (!expression) return 'Not set';
        
        if (type === 'cron') {
            // Try to make cron more readable
            const parts = expression.split(' ');
            if (parts.length === 5) {
                const [minute, hour, day, month, weekday] = parts;
                if (minute === '0' && hour !== '*' && day === '*' && month === '*' && weekday === '*') {
                    return `Daily at ${hour}:00`;
                }
                if (minute === '0' && hour === '*' && day === '*' && month === '*' && weekday === '*') {
                    return 'Every hour';
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
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Ready to Save
                        </Badge>
                    )}
                </div>
            </div>

            {/* Preview Content */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
                {/* Task Name */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Label className="text-sm font-medium text-muted-foreground">Task Name</Label>
                        {isFieldHighlighted('name') && (
                            <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="text-sm p-3 rounded">
                        {config.name || <span className="text-muted-foreground italic">No task name yet</span>}
                    </div>
                </div>

                {/* Description */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Label className="text-sm font-medium text-muted-foreground">Description</Label>
                        {isFieldHighlighted('description') && (
                            <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="text-sm p-3 rounded">
                        {config.description || <span className="text-muted-foreground italic">No description yet</span>}
                    </div>
                </div>

                {/* Schedule */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <label className="text-sm font-medium text-muted-foreground">Schedule</label>
                        {(isFieldHighlighted('schedule_type') || isFieldHighlighted('schedule_expression')) && (
                            <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded-lg border bg-card p-3 space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-muted-foreground">Type</span>
                            <span className="text-sm font-medium">{getScheduleTypeLabel(config.schedule_type)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-muted-foreground">Expression</span>
                            <span className="text-sm font-mono">{formatScheduleExpression(config.schedule_type, config.schedule_expression)}</span>
                        </div>
                        {config.timezone && (
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-muted-foreground">Timezone</span>
                                <span className="text-sm">{config.timezone}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Target Agent */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <label className="text-sm font-medium text-muted-foreground">Target Agent</label>
                        {isFieldHighlighted('target_agent_name') && (
                            <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded-lg border bg-card p-3">
                        <p className="text-sm font-medium">
                            {config.target_agent_name || <span className="text-muted-foreground italic">Not set</span>}
                        </p>
                    </div>
                </div>

                {/* Task Message */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-muted-foreground" />
                        <label className="text-sm font-medium text-muted-foreground">Task Message</label>
                        {isFieldHighlighted('task_message') && (
                            <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                                Updated
                            </Badge>
                        )}
                    </div>
                    <div className="rounded-lg border bg-card p-3">
                        <p className="text-sm whitespace-pre-wrap">
                            {config.task_message || <span className="text-muted-foreground italic">Not set</span>}
                        </p>
                    </div>
                </div>

                {/* Status */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <label className="text-sm font-medium text-muted-foreground">Status</label>
                    </div>
                    <div className="rounded-lg border bg-card p-3">
                        <div className="flex items-center gap-2">
                            <div className={`h-2 w-2 rounded-full ${config.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
                            <span className="text-sm">{config.enabled ? 'Enabled' : 'Disabled'}</span>
                        </div>
                    </div>
                </div>

                {/* Help Text */}
                {!isReadyToSave && (
                    <div className="rounded-lg bg-muted/50 p-4">
                        <p className="text-sm text-muted-foreground">
                            Continue chatting with the AI to refine your task configuration. 
                            When all required fields are set, you'll be able to save the task.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};