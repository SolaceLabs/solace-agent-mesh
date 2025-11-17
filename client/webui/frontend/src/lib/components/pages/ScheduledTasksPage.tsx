/**
 * Scheduled Tasks Management Page
 * Allows users to view, create, edit, and manage scheduled tasks
 */

import { useState, useEffect, useCallback } from "react";
import { Calendar, Clock, Play, Pause, Trash2, Plus, RefreshCw, AlertCircle, Pencil, Settings } from "lucide-react";
import { useScheduledTasks } from "@/lib/hooks/useScheduledTasks";
import { Button } from "@/lib/components/ui/button";
import type { ScheduledTask, CreateScheduledTaskRequest, ScheduleType } from "@/lib/types/scheduled-tasks";
import { TaskExecutionHistoryPage } from "./TaskExecutionHistoryPage";

// Schedule builder types
type FrequencyType = "daily" | "weekly" | "monthly" | "hourly" | "custom";

interface ScheduleConfig {
  frequency: FrequencyType;
  time: string; // HH:MM format
  ampm: "AM" | "PM";
  weekDays: number[]; // 0-6 (Sunday-Saturday)
  monthDay: number; // 1-31
  hourInterval: number; // 1, 2, 3, 6, 12, 24
}

// Convert schedule config to cron expression
function scheduleToCron(config: ScheduleConfig): string {
  const [hours24, minutes] = config.time.split(":").map(Number);
  let hour = hours24;
  
  // Convert 12-hour to 24-hour format
  if (config.ampm === "PM" && hour !== 12) {
    hour += 12;
  } else if (config.ampm === "AM" && hour === 12) {
    hour = 0;
  }

  switch (config.frequency) {
    case "daily":
      return `${minutes} ${hour} * * *`;
    
    case "weekly": {
      if (config.weekDays.length === 0) return `${minutes} ${hour} * * *`;
      const days = config.weekDays.sort().join(",");
      return `${minutes} ${hour} * * ${days}`;
    }
    
    case "monthly":
      return `${minutes} ${hour} ${config.monthDay} * *`;
    
    case "hourly":
      if (config.hourInterval === 24) {
        return `${minutes} ${hour} * * *`;
      }
      return `${minutes} */${config.hourInterval} * * *`;
    
    default:
      return `${minutes} ${hour} * * *`;
  }
}

// Parse cron expression to schedule config (best effort)
function cronToSchedule(cron: string): ScheduleConfig | null {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return null;

  const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
  
  // Parse time
  let hours24 = 9;
  let minutes = 0;
  
  if (hour !== "*" && !hour.includes("/")) {
    hours24 = parseInt(hour);
  }
  if (minute !== "*" && !minute.includes("/")) {
    minutes = parseInt(minute);
  }

  // Convert to 12-hour format
  let ampm: "AM" | "PM" = "AM";
  let hours12 = hours24;
  if (hours24 >= 12) {
    ampm = "PM";
    if (hours24 > 12) hours12 = hours24 - 12;
  } else if (hours24 === 0) {
    hours12 = 12;
  }

  const time = `${hours12.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

  // Detect frequency
  if (hour.includes("/")) {
    // Hourly pattern
    const interval = parseInt(hour.split("/")[1]);
    return {
      frequency: "hourly",
      time,
      ampm,
      weekDays: [],
      monthDay: 1,
      hourInterval: interval,
    };
  } else if (dayOfWeek !== "*") {
    // Weekly pattern
    const days = dayOfWeek.split(",").map(d => parseInt(d));
    return {
      frequency: "weekly",
      time,
      ampm,
      weekDays: days,
      monthDay: 1,
      hourInterval: 1,
    };
  } else if (dayOfMonth !== "*") {
    // Monthly pattern
    return {
      frequency: "monthly",
      time,
      ampm,
      weekDays: [],
      monthDay: parseInt(dayOfMonth),
      hourInterval: 1,
    };
  } else {
    // Daily pattern
    return {
      frequency: "daily",
      time,
      ampm,
      weekDays: [],
      monthDay: 1,
      hourInterval: 1,
    };
  }
}

export function ScheduledTasksPage() {
  const {
    isLoading,
    error,
    fetchTasks,
    createTask,
    updateTask,
    enableTask,
    disableTask,
    deleteTask,
  } = useScheduledTasks();

  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
  const [viewingTaskHistory, setViewingTaskHistory] = useState<ScheduledTask | null>(null);

  const loadTasks = useCallback(async () => {
    const response = await fetchTasks(currentPage, 20);
    if (response) {
      setTasks(response.tasks);
      setTotal(response.total);
    }
  }, [fetchTasks, currentPage]);

  // Load tasks on mount and page change
  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleCreateTask = async (taskData: CreateScheduledTaskRequest) => {
    const newTask = await createTask(taskData);
    if (newTask) {
      setShowCreateDialog(false);
      await loadTasks();
    }
  };

  const handleEditTask = (task: ScheduledTask) => {
    // Don't exit history view - just open the edit dialog
    setEditingTask(task);
    setShowEditDialog(true);
  };

  const handleUpdateTask = async (taskId: string, updates: Partial<CreateScheduledTaskRequest>) => {
    const updatedTask = await updateTask(taskId, updates);
    if (updatedTask) {
      setShowEditDialog(false);
      setEditingTask(null);
      
      // If we're viewing history, update the task in the history view
      if (viewingTaskHistory && viewingTaskHistory.id === taskId) {
        setViewingTaskHistory(updatedTask);
      }
      
      await loadTasks();
    }
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

  const formatSchedule = (task: ScheduledTask): string => {
    if (task.schedule_type === "cron") {
      return `Cron: ${task.schedule_expression}`;
    } else if (task.schedule_type === "interval") {
      return `Every ${task.schedule_expression}`;
    } else {
      return `Once at ${new Date(task.schedule_expression).toLocaleString()}`;
    }
  };

  const formatNextRun = (timestamp?: number): string => {
    if (!timestamp) return "Not scheduled";
    const date = new Date(timestamp);
    const now = new Date();
    const diff = date.getTime() - now.getTime();
    
    if (diff < 0) return "Overdue";
    if (diff < 60000) return "In < 1 minute";
    if (diff < 3600000) return `In ${Math.floor(diff / 60000)} minutes`;
    if (diff < 86400000) return `In ${Math.floor(diff / 3600000)} hours`;
    return `In ${Math.floor(diff / 86400000)} days`;
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

  // Show execution history as full page
  if (viewingTaskHistory) {
    return (
      <>
        <TaskExecutionHistoryPage
          task={viewingTaskHistory}
          onBack={() => setViewingTaskHistory(null)}
          onEdit={handleEditTask}
          onDelete={handleDeleteFromHistory}
        />
        
        {/* Edit Task Dialog - can be shown over history page */}
        {showEditDialog && editingTask && (
          <EditTaskDialog
            task={editingTask}
            onClose={() => {
              setShowEditDialog(false);
              setEditingTask(null);
            }}
            onUpdate={handleUpdateTask}
          />
        )}
      </>
    );
  }

  return (
    <div className="flex flex-col h-full p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Scheduled Tasks</h1>
          <p className="text-sm text-muted-foreground">
            Manage automated tasks and schedules
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadTasks}
            disabled={isLoading}
          >
            <RefreshCw className={`size-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => setShowCreateDialog(true)}
          >
            <Plus className="size-4 mr-2" />
            New Task
          </Button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="flex items-center gap-2 p-4 bg-destructive/10 text-destructive rounded-md">
          <AlertCircle className="size-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Tasks List */}
      <div className="flex-1 overflow-auto">
        {isLoading && tasks.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="size-8 animate-spin text-muted-foreground" />
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Calendar className="size-12 mb-4" />
            <p>No scheduled tasks yet</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => setShowCreateDialog(true)}
            >
              Create your first task
            </Button>
          </div>
        ) : (
          <div className="grid gap-4">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="border rounded-lg p-4 hover:bg-accent/50 transition-colors cursor-pointer"
                onClick={() => handleViewExecutions(task)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold">{task.name}</h3>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          task.enabled
                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                        }`}
                      >
                        {task.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    
                    {task.description && (
                      <p className="text-sm text-muted-foreground mb-2">
                        {task.description}
                      </p>
                    )}

                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="size-3" />
                        <span>{formatSchedule(task)}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="size-3" />
                        <span>Next: {formatNextRun(task.next_run_at)}</span>
                      </div>
                      <div>
                        <span>Agent: {task.target_agent_name}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEditTask(task)}
                      title="Edit task"
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleEnabled(task)}
                      title={task.enabled ? "Disable task" : "Enable task"}
                    >
                      {task.enabled ? (
                        <Pause className="size-4" />
                      ) : (
                        <Play className="size-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(task.id)}
                      title="Delete task"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-between border-t pt-4">
          <div className="text-sm text-muted-foreground">
            Showing {(currentPage - 1) * 20 + 1} to {Math.min(currentPage * 20, total)} of {total} tasks
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(p => p + 1)}
              disabled={currentPage * 20 >= total}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Create Task Dialog */}
      {showCreateDialog && (
        <CreateTaskDialog
          onClose={() => setShowCreateDialog(false)}
          onCreate={handleCreateTask}
        />
      )}

      {/* Edit Task Dialog */}
      {showEditDialog && editingTask && (
        <EditTaskDialog
          task={editingTask}
          onClose={() => {
            setShowEditDialog(false);
            setEditingTask(null);
          }}
          onUpdate={handleUpdateTask}
        />
      )}
    </div>
  );
}

/**
 * Schedule Builder Component
 * Google Calendar-style schedule builder with Simple and Advanced modes
 */
function ScheduleBuilder({
  value,
  onChange,
}: {
  value: string;
  onChange: (cron: string) => void;
}) {
  const [isAdvancedMode, setIsAdvancedMode] = useState(false);
  const [rawCron, setRawCron] = useState(value);
  
  // Initialize schedule config from cron or use defaults
  const initialConfig: ScheduleConfig = cronToSchedule(value) || {
    frequency: "daily",
    time: "09:00",
    ampm: "AM",
    weekDays: [],
    monthDay: 1,
    hourInterval: 1,
  };
  
  const [config, setConfig] = useState<ScheduleConfig>(initialConfig);

  // Update cron when config changes (Simple Mode)
  useEffect(() => {
    if (!isAdvancedMode) {
      const newCron = scheduleToCron(config);
      setRawCron(newCron);
      onChange(newCron);
    }
  }, [config, isAdvancedMode, onChange]);

  // Handle advanced mode cron changes
  const handleRawCronChange = (newCron: string) => {
    setRawCron(newCron);
    onChange(newCron);
  };

  // Toggle between modes
  const handleModeToggle = () => {
    if (!isAdvancedMode) {
      // Switching to advanced mode - use current cron
      setRawCron(scheduleToCron(config));
    } else {
      // Switching to simple mode - try to parse cron
      const parsed = cronToSchedule(rawCron);
      if (parsed) {
        setConfig(parsed);
      }
    }
    setIsAdvancedMode(!isAdvancedMode);
  };

  const updateConfig = (updates: Partial<ScheduleConfig>) => {
    setConfig({ ...config, ...updates });
  };

  if (isAdvancedMode) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium">Schedule (Cron Expression)</label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleModeToggle}
            className="text-xs"
          >
            <Calendar className="size-3 mr-1" />
            Simple Mode
          </Button>
        </div>
        <input
          type="text"
          className="w-full px-3 py-2 border rounded-md font-mono"
          value={rawCron}
          onChange={(e) => handleRawCronChange(e.target.value)}
          placeholder="0 9 * * *"
        />
        <p className="text-xs text-muted-foreground">
          Format: minute hour day month weekday
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium">Schedule</label>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleModeToggle}
          className="text-xs"
        >
          <Settings className="size-3 mr-1" />
          Advanced Mode
        </Button>
      </div>

      {/* Frequency Selector */}
      <div>
        <label className="block text-xs text-muted-foreground mb-2">Frequency</label>
        <select
          className="w-full px-3 py-2 border rounded-md"
          value={config.frequency}
          onChange={(e) => updateConfig({ frequency: e.target.value as FrequencyType })}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
          <option value="hourly">Every X hours</option>
          <option value="custom">Custom (Advanced)</option>
        </select>
      </div>

      {/* Hourly Interval */}
      {config.frequency === "hourly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Every</label>
          <select
            className="w-full px-3 py-2 border rounded-md"
            value={config.hourInterval}
            onChange={(e) => updateConfig({ hourInterval: parseInt(e.target.value) })}
          >
            <option value="1">1 hour</option>
            <option value="2">2 hours</option>
            <option value="3">3 hours</option>
            <option value="6">6 hours</option>
            <option value="12">12 hours</option>
            <option value="24">24 hours</option>
          </select>
        </div>
      )}

      {/* Time Picker (for non-hourly) */}
      {config.frequency !== "hourly" && config.frequency !== "custom" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Time</label>
          <div className="flex gap-2">
            <input
              type="time"
              className="flex-1 px-3 py-2 border rounded-md"
              value={config.time}
              onChange={(e) => {
                const [hours, minutes] = e.target.value.split(":");
                let h = parseInt(hours);
                const ampm = h >= 12 ? "PM" : "AM";
                if (h > 12) h -= 12;
                if (h === 0) h = 12;
                updateConfig({
                  time: `${h.toString().padStart(2, "0")}:${minutes}`,
                  ampm,
                });
              }}
            />
            <select
              className="px-3 py-2 border rounded-md"
              value={config.ampm}
              onChange={(e) => updateConfig({ ampm: e.target.value as "AM" | "PM" })}
            >
              <option value="AM">AM</option>
              <option value="PM">PM</option>
            </select>
          </div>
        </div>
      )}

      {/* Weekly Day Selector */}
      {config.frequency === "weekly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Days of Week</label>
          <div className="flex gap-2 flex-wrap">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  const newDays = config.weekDays.includes(idx)
                    ? config.weekDays.filter((d) => d !== idx)
                    : [...config.weekDays, idx];
                  updateConfig({ weekDays: newDays });
                }}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  config.weekDays.includes(idx)
                    ? "bg-primary text-primary-foreground"
                    : "bg-accent hover:bg-accent/80"
                }`}
              >
                {day}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Monthly Day Selector */}
      {config.frequency === "monthly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Day of Month</label>
          <select
            className="w-full px-3 py-2 border rounded-md"
            value={config.monthDay}
            onChange={(e) => updateConfig({ monthDay: parseInt(e.target.value) })}
          >
            {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Custom Mode Redirect */}
      {config.frequency === "custom" && (
        <div className="bg-accent/30 rounded-lg p-3 text-sm">
          <p className="mb-2">For custom schedules, please use Advanced Mode.</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleModeToggle}
          >
            Switch to Advanced Mode
          </Button>
        </div>
      )}

      {/* Preview */}
      {config.frequency !== "custom" && (
        <div className="bg-accent/30 rounded-lg p-3 text-sm">
          <p className="text-xs text-muted-foreground mb-1">Preview:</p>
          <p className="font-medium">{getScheduleDescription(config)}</p>
          <p className="text-xs text-muted-foreground mt-1 font-mono">
            Cron: {scheduleToCron(config)}
          </p>
        </div>
      )}
    </div>
  );
}

// Helper function to generate human-readable schedule description
function getScheduleDescription(config: ScheduleConfig): string {
  const timeStr = `${config.time} ${config.ampm}`;
  
  switch (config.frequency) {
    case "daily":
      return `Every day at ${timeStr}`;
    
    case "weekly": {
      if (config.weekDays.length === 0) return `Every day at ${timeStr}`;
      const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
      const days = config.weekDays.sort().map(d => dayNames[d]).join(", ");
      return `Every ${days} at ${timeStr}`;
    }
    
    case "monthly": {
      const suffix = config.monthDay === 1 ? "st" : config.monthDay === 2 ? "nd" : config.monthDay === 3 ? "rd" : "th";
      return `Monthly on the ${config.monthDay}${suffix} at ${timeStr}`;
    }
    
    case "hourly":
      if (config.hourInterval === 1) return "Every hour";
      if (config.hourInterval === 24) return `Every day at ${timeStr}`;
      return `Every ${config.hourInterval} hours`;
    
    default:
      return "Custom schedule";
  }
}

/**
 * Simple create task dialog
 */
function CreateTaskDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (data: CreateScheduledTaskRequest) => Promise<void>;
}) {
  const [formData, setFormData] = useState<CreateScheduledTaskRequest>({
    name: "",
    description: "",
    schedule_type: "cron",
    schedule_expression: "0 9 * * *",
    timezone: "UTC",
    target_agent_name: "OrchestratorAgent",
    task_message: [{ type: "text", text: "" }],
    enabled: true,
    timeout_seconds: 3600,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onCreate(formData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-background border rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">Create Scheduled Task</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Task Name</label>
            <input
              type="text"
              className="w-full px-3 py-2 border rounded-md"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              className="w-full px-3 py-2 border rounded-md"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={2}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Schedule Type</label>
            <select
              className="w-full px-3 py-2 border rounded-md"
              value={formData.schedule_type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  schedule_type: e.target.value as ScheduleType,
                  schedule_expression:
                    e.target.value === "cron"
                      ? "0 9 * * *"
                      : e.target.value === "interval"
                      ? "1h"
                      : new Date().toISOString(),
                })
              }
            >
              <option value="cron">Recurring Schedule</option>
              <option value="interval">Interval</option>
              <option value="one_time">One Time</option>
            </select>
          </div>

          {/* Schedule Builder for Cron */}
          {formData.schedule_type === "cron" && (
            <ScheduleBuilder
              value={formData.schedule_expression}
              onChange={(cron) => setFormData({ ...formData, schedule_expression: cron })}
            />
          )}

          {/* Interval Input */}
          {formData.schedule_type === "interval" && (
            <div>
              <label className="block text-sm font-medium mb-1">Interval (e.g., 30m, 1h)</label>
              <input
                type="text"
                className="w-full px-3 py-2 border rounded-md"
                value={formData.schedule_expression}
                onChange={(e) =>
                  setFormData({ ...formData, schedule_expression: e.target.value })
                }
                placeholder="30m"
                required
              />
            </div>
          )}

          {/* One Time Date Picker */}
          {formData.schedule_type === "one_time" && (
            <div>
              <label className="block text-sm font-medium mb-1">Date & Time</label>
              <input
                type="text"
                className="w-full px-3 py-2 border rounded-md"
                value={formData.schedule_expression}
                onChange={(e) =>
                  setFormData({ ...formData, schedule_expression: e.target.value })
                }
                placeholder="2025-12-25T09:00:00"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Target Agent</label>
            <input
              type="text"
              className="w-full px-3 py-2 border rounded-md"
              value={formData.target_agent_name}
              onChange={(e) =>
                setFormData({ ...formData, target_agent_name: e.target.value })
              }
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Task Message</label>
            <textarea
              className="w-full px-3 py-2 border rounded-md"
              value={formData.task_message[0]?.text || ""}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  task_message: [{ type: "text", text: e.target.value }],
                })
              }
              rows={3}
              placeholder="Enter the message to send to the agent..."
              required
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="enabled"
              checked={formData.enabled}
              onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
            />
            <label htmlFor="enabled" className="text-sm">
              Enable task immediately
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">Create</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Edit task dialog
 */
function EditTaskDialog({
  task,
  onClose,
  onUpdate,
}: {
  task: ScheduledTask;
  onClose: () => void;
  onUpdate: (taskId: string, updates: Partial<CreateScheduledTaskRequest>) => Promise<void>;
}) {
  const [formData, setFormData] = useState<Partial<CreateScheduledTaskRequest>>({
    name: task.name,
    description: task.description || "",
    schedule_type: task.schedule_type,
    schedule_expression: task.schedule_expression,
    timezone: task.timezone,
    target_agent_name: task.target_agent_name,
    task_message: task.task_message,
    enabled: task.enabled,
    timeout_seconds: task.timeout_seconds,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onUpdate(task.id, formData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-background border rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-4">Edit Scheduled Task</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Task Name</label>
            <input
              type="text"
              className="w-full px-3 py-2 border rounded-md"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              className="w-full px-3 py-2 border rounded-md"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={2}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Schedule Type</label>
            <select
              className="w-full px-3 py-2 border rounded-md"
              value={formData.schedule_type}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  schedule_type: e.target.value as ScheduleType,
                  schedule_expression:
                    e.target.value === "cron"
                      ? "0 9 * * *"
                      : e.target.value === "interval"
                      ? "1h"
                      : new Date().toISOString(),
                })
              }
            >
              <option value="cron">Recurring Schedule</option>
              <option value="interval">Interval</option>
              <option value="one_time">One Time</option>
            </select>
          </div>

          {/* Schedule Builder for Cron */}
          {formData.schedule_type === "cron" && (
            <ScheduleBuilder
              value={formData.schedule_expression || "0 9 * * *"}
              onChange={(cron) => setFormData({ ...formData, schedule_expression: cron })}
            />
          )}

          {/* Interval Input */}
          {formData.schedule_type === "interval" && (
            <div>
              <label className="block text-sm font-medium mb-1">Interval (e.g., 30m, 1h)</label>
              <input
                type="text"
                className="w-full px-3 py-2 border rounded-md"
                value={formData.schedule_expression || ""}
                onChange={(e) =>
                  setFormData({ ...formData, schedule_expression: e.target.value })
                }
                placeholder="30m"
                required
              />
            </div>
          )}

          {/* One Time Date Picker */}
          {formData.schedule_type === "one_time" && (
            <div>
              <label className="block text-sm font-medium mb-1">Date & Time</label>
              <input
                type="text"
                className="w-full px-3 py-2 border rounded-md"
                value={formData.schedule_expression || ""}
                onChange={(e) =>
                  setFormData({ ...formData, schedule_expression: e.target.value })
                }
                placeholder="2025-12-25T09:00:00"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Target Agent</label>
            <input
              type="text"
              className="w-full px-3 py-2 border rounded-md"
              value={formData.target_agent_name}
              onChange={(e) =>
                setFormData({ ...formData, target_agent_name: e.target.value })
              }
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Task Message</label>
            <textarea
              className="w-full px-3 py-2 border rounded-md"
              value={formData.task_message?.[0]?.text || ""}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  task_message: [{ type: "text", text: e.target.value }],
                })
              }
              rows={3}
              placeholder="Enter the message to send to the agent..."
              required
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="edit-enabled"
              checked={formData.enabled}
              onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
            />
            <label htmlFor="edit-enabled" className="text-sm">
              Enable task
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">Update Task</Button>
          </div>
        </form>
      </div>
    </div>
  );
}