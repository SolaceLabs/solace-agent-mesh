import React, { useState, useMemo } from "react";
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
}

export const TaskCards: React.FC<TaskCardsProps> = ({
    tasks,
    onManualCreate,
    onAIAssisted,
    onEdit,
    onDelete,
    onToggleEnabled,
    onViewExecutions,
}) => {
    const [selectedTask, setSelectedTask] = useState<ScheduledTask | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
    const [showStatusDropdown, setShowStatusDropdown] = useState(false);

    const handleTaskClick = (task: ScheduledTask) => {
        setSelectedTask(prev => (prev?.id === task.id ? null : task));
    };

    const handleCloseSidePanel = () => {
        setSelectedTask(null);
    };

    const statuses = ["Enabled", "Disabled"];

    const filteredTasks = useMemo(() => {
        const filtered = tasks.filter(task => {
            const matchesSearch =
                task.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                task.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                task.target_agent_name?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesStatus =
                selectedStatuses.length === 0 ||
                (task.enabled && selectedStatuses.includes("Enabled")) ||
                (!task.enabled && selectedStatuses.includes("Disabled"));

            return matchesSearch && matchesStatus;
        });

        return filtered.sort((a, b) => {
            // Sort by enabled status first (enabled tasks first)
            if (a.enabled !== b.enabled) {
                return a.enabled ? -1 : 1;
            }
            // Then sort alphabetically by name
            const nameA = (a.name || "").toLowerCase();
            const nameB = (b.name || "").toLowerCase();
            return nameA.localeCompare(nameB);
        });
    }, [tasks, searchQuery, selectedStatuses]);

    const toggleStatus = (status: string) => {
        setSelectedStatuses(prev =>
            prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]
        );
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
                    <div className="flex h-full flex-col pt-6 pb-6 pl-6">
            {!isLibraryEmpty && (
                <div className="mb-4 flex items-center gap-2">
                    <SearchInput
                        value={searchQuery}
                        onChange={setSearchQuery}
                        placeholder="Filter by name, description, or agent..."
                        testid="taskSearchInput"
                    />

                    {/* Status Filter Dropdown */}
                    <div className="relative">
                        <Button
                            onClick={() => setShowStatusDropdown(!showStatusDropdown)}
                            variant="outline"
                            testid="taskStatusFilter"
                        >
                            <Filter size={16} />
                            Status
                            {selectedStatuses.length > 0 && (
                                <span className="bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs">
                                    {selectedStatuses.length}
                                </span>
                            )}
                        </Button>

                        {showStatusDropdown && (
                            <>
                                {/* Backdrop */}
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setShowStatusDropdown(false)}
                                />

                                {/* Dropdown */}
                                <div className="bg-background absolute top-full left-0 z-20 mt-1 max-h-[300px] min-w-[200px] overflow-y-auto rounded-md border shadow-lg">
                                    {selectedStatuses.length > 0 && (
                                        <div className="border-b">
                                            <button
                                                onClick={clearStatuses}
                                                className="text-muted-foreground hover:text-foreground hover:bg-muted flex min-h-[24px] w-full cursor-pointer items-center gap-1 px-3 py-2 text-left text-xs transition-colors"
                                            >
                                                <X size={14} />
                                                {selectedStatuses.length === 1 ? "Clear Filter" : "Clear Filters"}
                                            </button>
                                        </div>
                                    )}
                                    <div className="p-1">
                                        {statuses.map(status => (
                                            <label
                                                key={status}
                                                className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded px-2 py-1.5"
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={selectedStatuses.includes(status)}
                                                    onChange={() => toggleStatus(status)}
                                                    className="rounded"
                                                />
                                                <span className="text-sm">{status}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    {hasActiveFilters && (
                        <Button
                            variant="ghost"
                            onClick={clearAllFilters}
                            data-testid="clearAllFiltersButton"
                        >
                            <X size={16} />
                            Clear All
                        </Button>
                    )}
                </div>
            )}

            {filteredTasks.length === 0 && searchQuery ? (
                <EmptyState
                    title="No Tasks Match Your Filter"
                    subtitle="Try adjusting your filter terms."
                    variant="notFound"
                    buttons={[
                        {
                            text: "Clear Filter",
                            variant: "default",
                            onClick: () => setSearchQuery(""),
                        },
                    ]}
                />
            ) : isLibraryEmpty ? (
                <EmptyState
                    title="No Scheduled Tasks Found"
                    subtitle="Create scheduled tasks to automate agent workflows."
                    variant="noImage"
                    buttons={createButtons}
                />
            ) : (
                <div className="flex-1 overflow-y-auto">
                    <div className="flex flex-wrap gap-6">
                        <CreateTaskCard onManualCreate={onManualCreate} onAIAssisted={onAIAssisted} />

                        {/* Existing Task Cards */}
                        {filteredTasks.map(task => (
                            <TaskCard
                                key={task.id}
                                task={task}
                                isSelected={selectedTask?.id === task.id}
                                onTaskClick={() => handleTaskClick(task)}
                                onEdit={onEdit}
                                onDelete={onDelete}
                                onToggleEnabled={onToggleEnabled}
                                onViewExecutions={onViewExecutions}
                            />
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
                                onDelete={(taskId) => {
                                    onDelete(taskId);
                                    handleCloseSidePanel();
                                }}
                                onViewExecutions={onViewExecutions}
                                onToggleEnabled={onToggleEnabled}
                            />
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};