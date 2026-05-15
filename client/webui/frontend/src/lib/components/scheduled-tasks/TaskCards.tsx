import React, { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { X, Filter } from "lucide-react";

import type { ScheduledTask } from "@/lib/types/scheduled-tasks";

import { TaskCard } from "./TaskCard";
import { CreateTaskCard } from "./CreateTaskCard";
import { TaskDetailSidePanel } from "./TaskDetailSidePanel";
import { EmptyState } from "../common";
import { Button, SearchInput } from "@/lib/components/ui";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";

interface TaskCardsProps {
    tasks: ScheduledTask[];
    onManualCreate: () => void;
    onAIAssisted: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (taskId: string) => void;
    onToggleEnabled: (task: ScheduledTask) => void;
    onViewExecutions: (task: ScheduledTask) => void;
    onRunNow?: (task: ScheduledTask) => void;
    runNowPendingTaskId?: string | null;
}

export const TaskCards: React.FC<TaskCardsProps> = ({ tasks, onManualCreate, onAIAssisted, onEdit, onDelete, onToggleEnabled, onViewExecutions, onRunNow, runNowPendingTaskId }) => {
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
    const [showStatusDropdown, setShowStatusDropdown] = useState(false);

    // Deep-link support: /schedules?taskId=<id> selects and scrolls to that
    // task (used by the session-card badge in /recent-chats). We consume the
    // param once and strip it so a browser-back doesn't re-trigger selection.
    const [searchParams, setSearchParams] = useSearchParams();
    useEffect(() => {
        const deeplinkTaskId = searchParams.get("taskId");
        if (!deeplinkTaskId) return;
        if (tasks.some(t => t.id === deeplinkTaskId)) {
            setSelectedTaskId(deeplinkTaskId);
            // Defer scroll until the card is rendered
            requestAnimationFrame(() => {
                document.querySelector(`[data-task-id="${deeplinkTaskId}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
            });
            const next = new URLSearchParams(searchParams);
            next.delete("taskId");
            setSearchParams(next, { replace: true });
        }
    }, [searchParams, setSearchParams, tasks]);

    const selectedTask = useMemo(() => tasks.find(t => t.id === selectedTaskId) ?? null, [tasks, selectedTaskId]);

    const handleTaskClick = (task: ScheduledTask) => {
        setSelectedTaskId(prev => (prev === task.id ? null : task.id));
    };

    const handleCloseSidePanel = () => {
        setSelectedTaskId(null);
    };

    const statuses = ["Active", "Paused", "Error"];

    const filteredTasks = useMemo(() => {
        const statusMap: Record<string, string> = { Active: "active", Paused: "paused", Error: "error" };
        const selectedStatusValues = selectedStatuses.map(s => statusMap[s]);

        const filtered = tasks.filter(task => {
            const matchesSearch = task.name?.toLowerCase().includes(searchQuery.toLowerCase()) || task.description?.toLowerCase().includes(searchQuery.toLowerCase()) || task.targetAgentName?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesStatus = selectedStatusValues.length === 0 || selectedStatusValues.includes(task.status);

            return matchesSearch && matchesStatus;
        });

        const statusOrder: Record<string, number> = { active: 0, paused: 1, error: 2 };
        return filtered.sort((a, b) => {
            // Sort by status first (active > paused > error)
            const statusDiff = (statusOrder[a.status] ?? 3) - (statusOrder[b.status] ?? 3);
            if (statusDiff !== 0) return statusDiff;
            // Then sort alphabetically by name
            const nameA = (a.name || "").toLowerCase();
            const nameB = (b.name || "").toLowerCase();
            return nameA.localeCompare(nameB);
        });
    }, [tasks, searchQuery, selectedStatuses]);

    const toggleStatus = (status: string) => {
        setSelectedStatuses(prev => (prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]));
    };

    const clearStatuses = () => {
        setSelectedStatuses([]);
    };

    const clearAllFilters = () => {
        setSearchQuery("");
        setSelectedStatuses([]);
    };

    const hasActiveFilters = searchQuery.length > 0 || selectedStatuses.length > 0;
    const isLibraryEmpty = tasks.length === 0;

    const createButtons = useMemo(() => {
        return [
            {
                text: "Build with AI",
                variant: "default" as const,
                onClick: onAIAssisted,
            },
            {
                text: "Create Manually",
                variant: "outline" as const,
                onClick: onManualCreate,
            },
        ];
    }, [onAIAssisted, onManualCreate]);

    return (
        <div className="absolute inset-0 h-full w-full">
            <ResizablePanelGroup direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={selectedTask ? 70 : 100} minSize={50} maxSize={selectedTask ? 100 : 100} id="taskCardsMainPanel">
                    <div className="flex h-full flex-col px-4 py-4 sm:pt-6 sm:pr-0 sm:pb-6 sm:pl-6">
                        {!isLibraryEmpty && (
                            <div className="mb-4 flex flex-wrap items-center gap-2">
                                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name, description, or agent..." testid="taskSearchInput" />

                                {/* Status Filter Dropdown */}
                                <div className="relative">
                                    <Button onClick={() => setShowStatusDropdown(!showStatusDropdown)} variant="outline" testid="taskStatusFilter">
                                        <Filter size={16} />
                                        Status
                                        {selectedStatuses.length > 0 && <span className="rounded-full bg-(--primary-wMain) px-2 py-0.5 text-xs text-(--primary-text-w10)">{selectedStatuses.length}</span>}
                                    </Button>

                                    {showStatusDropdown && (
                                        <>
                                            {/* Backdrop */}
                                            <div className="fixed inset-0 z-40" onClick={() => setShowStatusDropdown(false)} />

                                            {/* Dropdown — anchored to the right edge of the trigger so it doesn't overflow viewport on mobile */}
                                            <div className="absolute top-full right-0 z-50 mt-1 max-h-[300px] min-w-[200px] overflow-y-auto rounded-md border border-(--secondary-w20) bg-(--background-w10) p-1 shadow-md sm:right-auto sm:left-0">
                                                {selectedStatuses.length > 0 && (
                                                    <div className="border-b">
                                                        <button
                                                            onClick={clearStatuses}
                                                            className="flex min-h-[24px] w-full cursor-pointer items-center gap-1 px-3 py-2 text-left text-xs text-(--secondary-text-wMain) transition-colors hover:bg-(--secondary-w10) hover:text-(--primary-text-wMain)"
                                                        >
                                                            <X size={14} />
                                                            {selectedStatuses.length === 1 ? "Clear Filter" : "Clear Filters"}
                                                        </button>
                                                    </div>
                                                )}
                                                <div className="p-1">
                                                    {statuses.map(status => (
                                                        <label key={status} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-(--secondary-w10)">
                                                            <input type="checkbox" checked={selectedStatuses.includes(status)} onChange={() => toggleStatus(status)} className="rounded" />
                                                            <span className="text-sm">{status}</span>
                                                        </label>
                                                    ))}
                                                </div>
                                            </div>
                                        </>
                                    )}
                                </div>

                                {hasActiveFilters && (
                                    <Button variant="ghost" onClick={clearAllFilters} data-testid="clearAllFiltersButton">
                                        <X size={16} />
                                        Clear All
                                    </Button>
                                )}
                            </div>
                        )}

                        {filteredTasks.length === 0 && hasActiveFilters ? (
                            <EmptyState
                                title="No Tasks Match Your Filter"
                                subtitle="Try adjusting your filter terms."
                                variant="notFound"
                                buttons={[
                                    {
                                        text: "Clear All Filters",
                                        variant: "default",
                                        onClick: clearAllFilters,
                                    },
                                ]}
                            />
                        ) : isLibraryEmpty ? (
                            <EmptyState title="No Scheduled Tasks Found" subtitle="Create scheduled tasks to automate agent workflows." variant="noImage" buttons={createButtons} />
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <div className="flex flex-wrap gap-6">
                                    <CreateTaskCard onManualCreate={onManualCreate} onAIAssisted={onAIAssisted} />

                                    {/* Existing Task Cards */}
                                    {filteredTasks.map(task => (
                                        <div key={task.id} data-task-id={task.id} className="w-full sm:w-auto">
                                            <TaskCard
                                                task={task}
                                                isSelected={selectedTask?.id === task.id}
                                                onTaskClick={() => handleTaskClick(task)}
                                                onEdit={onEdit}
                                                onDelete={onDelete}
                                                onToggleEnabled={onToggleEnabled}
                                                onViewExecutions={onViewExecutions}
                                                onRunNow={onRunNow}
                                                isRunNowPending={runNowPendingTaskId === task.id}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </ResizablePanel>

                {/* Side Panel - resizable */}
                {selectedTask && (
                    <>
                        <ResizableHandle />
                        <ResizablePanel defaultSize={30} minSize={20} maxSize={50} id="taskDetailSidePanel">
                            <TaskDetailSidePanel
                                task={selectedTask}
                                onClose={handleCloseSidePanel}
                                onEdit={onEdit}
                                onDelete={taskId => {
                                    onDelete(taskId);
                                    handleCloseSidePanel();
                                }}
                                onViewExecutions={onViewExecutions}
                                onToggleEnabled={onToggleEnabled}
                                onRunNow={onRunNow}
                                isRunNowPending={runNowPendingTaskId === selectedTask.id}
                            />
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};
