/**
 * Scheduled Tasks Management Page
 * Allows users to view, create, edit, and manage scheduled tasks
 */

import { useState } from "react";
import { RefreshCw, AlertCircle } from "lucide-react";
import { useScheduledTasks, useEnableScheduledTask, useDisableScheduledTask, useDeleteScheduledTask, useRunScheduledTaskNow } from "@/lib/api/scheduled-tasks";
import { Button } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";
import { TaskExecutionHistoryPage } from "./TaskExecutionHistoryPage";
import { TaskTemplateBuilder } from "@/lib/components/scheduled-tasks/TaskTemplateBuilder";
import { GenerateTaskDialog } from "@/lib/components/scheduled-tasks/GenerateTaskDialog";
import { TaskCards } from "@/lib/components/scheduled-tasks/TaskCards";
import { Header, EmptyState, ConfirmationDialog, PageLayout } from "@/lib/components";
import { LifecycleBadge } from "@/lib/components/ui";

export function ScheduledTasksPage() {
    const { data: tasksResponse, isLoading, error, refetch: loadTasks } = useScheduledTasks();
    const enableTaskMutation = useEnableScheduledTask();
    const disableTaskMutation = useDisableScheduledTask();
    const deleteTaskMutation = useDeleteScheduledTask();
    const runNowMutation = useRunScheduledTaskNow();
    const { addNotification } = useChatContext();

    const tasks = tasksResponse?.tasks ?? [];

    const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
    const [viewingTaskHistory, setViewingTaskHistory] = useState<ScheduledTask | null>(null);
    const [showBuilder, setShowBuilder] = useState(false);
    const [showGenerateDialog, setShowGenerateDialog] = useState(false);
    const [initialMessage, setInitialMessage] = useState<string | null>(null);
    const [builderInitialMode, setBuilderInitialMode] = useState<"manual" | "ai-assisted">("ai-assisted");
    const [deleteConfirm, setDeleteConfirm] = useState<{ taskId: string; taskName: string; source: "list" | "history" } | null>(null);

    const handleEditTask = (task: ScheduledTask) => {
        setEditingTask(task);
        setBuilderInitialMode("manual");
        setShowBuilder(true);
    };

    const handleToggleEnabled = async (task: ScheduledTask) => {
        if (task.enabled) {
            await disableTaskMutation.mutateAsync(task.id);
        } else {
            await enableTaskMutation.mutateAsync(task.id);
        }
    };

    const handleDelete = (taskId: string) => {
        const task = tasks.find(t => t.id === taskId);
        setDeleteConfirm({ taskId, taskName: task?.name || "this task", source: "list" });
    };

    const handleViewExecutions = (task: ScheduledTask) => {
        setViewingTaskHistory(task);
    };

    const handleDeleteFromHistory = (taskId: string, taskName: string) => {
        setDeleteConfirm({ taskId, taskName, source: "history" });
    };

    const handleConfirmDelete = async () => {
        if (!deleteConfirm) return;
        try {
            await deleteTaskMutation.mutateAsync(deleteConfirm.taskId);
            if (deleteConfirm.source === "history") {
                setViewingTaskHistory(null);
            }
        } finally {
            setDeleteConfirm(null);
        }
    };

    const handleGenerateTask = (taskDescription: string) => {
        setInitialMessage(taskDescription);
        setShowGenerateDialog(false);
        setBuilderInitialMode("ai-assisted");
        setShowBuilder(true);
    };

    const handleRunNow = async (task: ScheduledTask) => {
        try {
            await runNowMutation.mutateAsync(task.id);
            addNotification(`"${task.name}" started — check execution history for results.`, "success");
        } catch (err: unknown) {
            // Prefer the server-provided detail when available (e.g. 409 "already running").
            const message = (err instanceof Error && err.message) || "Failed to run task";
            addNotification(`Run Now failed: ${message}`, "warning");
        }
    };

    // Show task builder/editor as full page
    if (showBuilder) {
        return (
            <>
                <TaskTemplateBuilder
                    onBack={() => {
                        setShowBuilder(false);
                        setInitialMessage(null);
                        setEditingTask(null);
                    }}
                    onSuccess={async () => {
                        const wasEditingTask = editingTask;
                        setShowBuilder(false);
                        setInitialMessage(null);
                        setEditingTask(null);
                        const { data: refreshed } = await loadTasks();

                        // If we were editing from history view, return to history
                        if (wasEditingTask && viewingTaskHistory && viewingTaskHistory.id === wasEditingTask.id) {
                            const updatedTask = refreshed?.tasks.find(t => t.id === wasEditingTask.id);
                            if (updatedTask) {
                                setViewingTaskHistory(updatedTask);
                            }
                        }
                    }}
                    initialMessage={initialMessage}
                    initialMode={builderInitialMode}
                    editingTask={editingTask}
                    isEditing={!!editingTask}
                />
            </>
        );
    }

    // Show execution history as full page
    if (viewingTaskHistory) {
        return (
            <>
                <TaskExecutionHistoryPage task={viewingTaskHistory} onBack={() => setViewingTaskHistory(null)} onEdit={handleEditTask} onDelete={handleDeleteFromHistory} />
                <ConfirmationDialog
                    open={!!deleteConfirm}
                    title="Delete Scheduled Task"
                    description={`Are you sure you want to delete "${deleteConfirm?.taskName}"?`}
                    onOpenChange={open => {
                        if (!open) setDeleteConfirm(null);
                    }}
                    onConfirm={handleConfirmDelete}
                    actionLabels={{ confirm: "Delete", cancel: "Cancel" }}
                />
            </>
        );
    }

    return (
        <PageLayout>
            <Header
                title={
                    <>
                        Scheduled Tasks <LifecycleBadge>EXPERIMENTAL</LifecycleBadge>
                    </>
                }
                buttons={[
                    <Button data-testid="refreshTasks" disabled={isLoading} variant="ghost" tooltip="Refresh Tasks" onClick={() => loadTasks()}>
                        <RefreshCw className="size-4" />
                        Refresh
                    </Button>,
                ]}
            />

            {/* Error Display */}
            {error && (
                <div className="mx-6 mt-4 flex items-center gap-2 rounded-md bg-(--error-w10) p-4 text-(--error-wMain)">
                    <AlertCircle className="size-4" />
                    <span>{error.message}</span>
                </div>
            )}

            {isLoading && tasks.length === 0 ? (
                <EmptyState title="Loading tasks..." variant="loading" />
            ) : (
                <div className="relative flex-1 p-4">
                    <TaskCards
                        tasks={tasks}
                        onManualCreate={() => {
                            setBuilderInitialMode("manual");
                            setShowBuilder(true);
                        }}
                        onAIAssisted={() => setShowGenerateDialog(true)}
                        onEdit={handleEditTask}
                        onDelete={handleDelete}
                        onToggleEnabled={handleToggleEnabled}
                        onViewExecutions={handleViewExecutions}
                        onRunNow={handleRunNow}
                        runNowPendingTaskId={runNowMutation.isPending ? ((runNowMutation.variables as string | undefined) ?? null) : null}
                    />
                </div>
            )}

            {/* Generate Task Dialog */}
            <GenerateTaskDialog isOpen={showGenerateDialog} onClose={() => setShowGenerateDialog(false)} onGenerate={handleGenerateTask} />

            {/* Delete Confirmation Dialog */}
            <ConfirmationDialog
                open={!!deleteConfirm}
                title="Delete Scheduled Task"
                description={`Are you sure you want to delete "${deleteConfirm?.taskName}"?`}
                onOpenChange={open => {
                    if (!open) setDeleteConfirm(null);
                }}
                onConfirm={handleConfirmDelete}
                actionLabels={{ confirm: "Delete", cancel: "Cancel" }}
            />
        </PageLayout>
    );
}
