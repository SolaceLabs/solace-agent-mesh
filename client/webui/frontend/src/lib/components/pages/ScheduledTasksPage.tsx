/**
 * Scheduled Tasks Management Page
 * Allows users to view, create, edit, and manage scheduled tasks
 */

import { useState, useEffect, useCallback } from "react";
import { RefreshCw, AlertCircle } from "lucide-react";
import { useScheduledTasks } from "@/lib/hooks/useScheduledTasks";
import { Button } from "@/lib/components/ui";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";
import { TaskExecutionHistoryPage } from "./TaskExecutionHistoryPage";
import { TaskTemplateBuilder } from "@/lib/components/scheduled-tasks/TaskTemplateBuilder";
import { GenerateTaskDialog } from "@/lib/components/scheduled-tasks/GenerateTaskDialog";
import { TaskCards } from "@/lib/components/scheduled-tasks/TaskCards";
import { Header, EmptyState } from "@/lib/components";

export function ScheduledTasksPage() {
  const {
    isLoading,
    error,
    fetchTasks,
    enableTask,
    disableTask,
    deleteTask,
  } = useScheduledTasks();

  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
  const [viewingTaskHistory, setViewingTaskHistory] = useState<ScheduledTask | null>(null);
  const [showBuilder, setShowBuilder] = useState(false);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [initialMessage, setInitialMessage] = useState<string | null>(null);
  const [builderInitialMode, setBuilderInitialMode] = useState<"manual" | "ai-assisted">("ai-assisted");

  const loadTasks = useCallback(async () => {
    const response = await fetchTasks(1, 100); // Load all tasks for card view
    if (response) {
      setTasks(response.tasks);
    }
  }, [fetchTasks]);

  // Load tasks on mount and page change
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleEditTask = (task: ScheduledTask) => {
    // Navigate to edit page (TaskTemplateBuilder in edit mode)
    setEditingTask(task);
    setBuilderInitialMode("manual");
    setShowBuilder(true);
  };

  const handleToggleEnabled = async (task: ScheduledTask) => {
    const success = task.enabled
      ? await disableTask(task.id)
      : await enableTask(task.id);
    
    if (success) {
      await loadTasks();
    }
  };

  const handleDelete = async (taskId: string) => {
    if (confirm("Are you sure you want to delete this scheduled task?")) {
      const success = await deleteTask(taskId);
      if (success) {
        await loadTasks();
      }
    }
  };

  const handleViewExecutions = (task: ScheduledTask) => {
    setViewingTaskHistory(task);
  };

  const handleDeleteFromHistory = (taskId: string, taskName: string) => {
    if (confirm(`Are you sure you want to delete "${taskName}"?`)) {
      deleteTask(taskId).then(success => {
        if (success) {
          setViewingTaskHistory(null);
          loadTasks();
        }
      });
    }
  };

  const handleGenerateTask = (taskDescription: string) => {
    setInitialMessage(taskDescription);
    setShowGenerateDialog(false);
    setBuilderInitialMode("ai-assisted");
    setShowBuilder(true);
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
            await loadTasks();
            
            // If we were editing from history view, return to history
            if (wasEditingTask && viewingTaskHistory && viewingTaskHistory.id === wasEditingTask.id) {
              // Refresh the task data for history view
              const response = await fetchTasks(1, 100);
              if (response) {
                const updatedTask = response.tasks.find(t => t.id === wasEditingTask.id);
                if (updatedTask) {
                  setViewingTaskHistory(updatedTask);
                }
              }
            }
          }}
          initialMessage={initialMessage}
          initialMode={builderInitialMode}
          editingTask={editingTask}
          isEditing={!!editingTask}
        />
        
        {/* Generate Task Dialog */}
        <GenerateTaskDialog
          isOpen={showGenerateDialog}
          onClose={() => setShowGenerateDialog(false)}
          onGenerate={handleGenerateTask}
        />
      </>
    );
  }

  // Show execution history as full page
  if (viewingTaskHistory) {
    return (
      <TaskExecutionHistoryPage
        task={viewingTaskHistory}
        onBack={() => setViewingTaskHistory(null)}
        onEdit={handleEditTask}
        onDelete={handleDeleteFromHistory}
      />
    );
  }

  return (
    <div className="flex h-full w-full flex-col">
      <Header
        title="Scheduled Tasks"
        buttons={[
          <Button
            data-testid="refreshTasks"
            disabled={isLoading}
            variant="ghost"
            tooltip="Refresh Tasks"
            onClick={loadTasks}
          >
            <RefreshCw className="size-4" />
            Refresh
          </Button>,
        ]}
      />

      {/* Error Display */}
      {error && (
        <div className="flex items-center gap-2 p-4 mx-6 mt-4 bg-destructive/10 text-destructive rounded-md">
          <AlertCircle className="size-4" />
          <span>{error}</span>
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
          />
        </div>
      )}

      {/* Generate Task Dialog */}
      <GenerateTaskDialog
        isOpen={showGenerateDialog}
        onClose={() => setShowGenerateDialog(false)}
        onGenerate={handleGenerateTask}
      />
    </div>
  );
}