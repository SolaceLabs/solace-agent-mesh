/**
 * Task Execution History page.
 *
 * Layout (matches the redesign mock):
 *   ┌──────────────┬────────────────────────────────────────────┐
 *   │              │  Latest Execution                          │
 *   │ Configuration│   Status • Completed On • Duration • [Chat]│
 *   │  (sidebar)   │   Output Summary                           │
 *   │              │                                            │
 *   │              │  Execution History (sortable, paginated)   │
 *   │              │   row click → opens that run's chat session│
 *   └──────────────┴────────────────────────────────────────────┘
 */

import React, { useState } from "react";
import { MessageSquare, MoreHorizontal, Trash2 } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import type { ScheduledTask, TaskExecution } from "@/lib/types/scheduled-tasks";
import { Header } from "@/lib/components/header";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import { useTaskExecutions, useExecution, useRunScheduledTaskNow, useEnableScheduledTask, useDisableScheduledTask, useDeleteExecution } from "@/lib/api/scheduled-tasks";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import { IN_PROGRESS_STATUSES } from "@/lib/components/scheduled-tasks/StatusBadge";
import { ConfigurationSidebar, LatestExecutionPanel, ExecutionDetailPanel, ExecutionHistoryTable, PAGE_SIZE, formatExecutionLabel } from "@/lib/components/scheduled-tasks/execution-history";

interface TaskExecutionHistoryPageProps {
    task: ScheduledTask;
    onBack: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (id: string, name: string) => void;
}

export const TaskExecutionHistoryPage: React.FC<TaskExecutionHistoryPageProps> = ({ task, onBack, onEdit, onDelete }) => {
    const navigate = useNavigate();
    const { handleSwitchSession } = useChatContext();
    const [page, setPage] = useState(1);
    const [filterFrom, setFilterFrom] = useState("");
    const [filterTo, setFilterTo] = useState("");

    // Convert YYYY-MM-DD → epoch ms in the user's *browser* timezone — that's
    // the same timezone the row timestamps render in, so picking "May 4" in
    // the filter matches the rows whose displayed Completed On is May 4.
    // "From" is start-of-day, "To" is end-of-day so a single date inclusively
    // covers all runs that day.
    const filterFromMs = filterFrom ? new Date(`${filterFrom}T00:00:00`).getTime() : null;
    const filterToMs = filterTo ? new Date(`${filterTo}T23:59:59.999`).getTime() : null;

    // Reset page in the same handler that updates the filter so we don't fire
    // a query with the stale page first and then a second query after a
    // useEffect resets it.
    const handleFilterFromChange = (value: string) => {
        setFilterFrom(value);
        setPage(1);
    };
    const handleFilterToChange = (value: string) => {
        setFilterTo(value);
        setPage(1);
    };

    const { data, isLoading } = useTaskExecutions(task.id, page, PAGE_SIZE, filterFromMs, filterToMs, { poll: true });
    const executions = data?.executions ?? [];
    const totalCount = data?.total ?? executions.length;

    // The "Latest Execution" panel and the Configuration sidebar's snapshot
    // must reflect the actual most recent run, independent of the table's
    // current page or date filter. Fetch page 1, size 1, unfiltered.
    const { data: latestData } = useTaskExecutions(task.id, 1, 1, null, null, { poll: true });
    const latestExecutionFromQuery = latestData?.executions?.[0] ?? null;

    const runNowMutation = useRunScheduledTaskNow();
    const enableMutation = useEnableScheduledTask();
    const disableMutation = useDisableScheduledTask();
    const deleteExecutionMutation = useDeleteExecution(task.id);
    const [executionToDelete, setExecutionToDelete] = useState<TaskExecution | null>(null);

    // Selection is URL-driven via ?execution=<id> so the detail view is
    // deep-linkable and survives list refetches that move the row to another
    // page or filter window.
    const [searchParams, setSearchParams] = useSearchParams();
    const selectedExecutionId = searchParams.get("execution");
    // Per-execution query keeps the detail view alive independent of the
    // list — survives page changes, filter changes, and refetches that move
    // the row out of the current window.
    const { data: selectedExecutionFromQuery } = useExecution(selectedExecutionId, { poll: true });

    const handleSelectExecution = (executionId: string) => {
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            next.set("execution", executionId);
            return next;
        });
    };
    const handleClearSelection = () => {
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            next.delete("execution");
            return next;
        });
    };
    const [detailTab, setDetailTab] = useState<"output" | "artifacts">("output");

    // Polling cadence is driven by useTaskExecutions / useExecution
    // ({ poll: true }) — adaptive 5s/30s based on whether the execution is in
    // flight, plus refetch on window focus.
    const latestExecution = latestExecutionFromQuery;
    // Prefer the per-execution query (canonical source) but fall back to any
    // matching row in the list/latest queries while the dedicated query is
    // first loading, so the detail panel never flashes empty.
    const selectedExecution: TaskExecution | null = selectedExecutionId
        ? (selectedExecutionFromQuery ?? executions.find(e => e.id === selectedExecutionId) ?? (latestExecutionFromQuery?.id === selectedExecutionId ? latestExecutionFromQuery : null) ?? null)
        : null;
    // The Configuration sidebar reflects the currently-displayed execution's
    // snapshot — latest by default, or the row the user opened.
    const displayedExecution = selectedExecution ?? latestExecution;

    const handleGoToChat = async (executionId: string) => {
        await handleSwitchSession(`scheduled_${executionId}`);
        navigate("/chat");
    };

    const breadcrumbs = selectedExecution
        ? [{ label: "Scheduled Tasks", onClick: onBack }, { label: task.name, onClick: handleClearSelection }, { label: formatExecutionLabel(selectedExecution) }]
        : [{ label: "Scheduled Tasks", onClick: onBack }, { label: task.name }];

    const headerTitle = selectedExecution ? formatExecutionLabel(selectedExecution) : task.name;

    const headerButtons = selectedExecution
        ? [
              <Button key="view-chat" onClick={() => handleGoToChat(selectedExecution.id)} disabled={IN_PROGRESS_STATUSES.has(selectedExecution.status) && !selectedExecution.startedAt}>
                  <MessageSquare className="mr-2 h-4 w-4" />
                  View Chat Output
              </Button>,
              <DropdownMenu key="actions">
                  <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8" tooltip="Actions">
                          <MoreHorizontal className="h-4 w-4" />
                      </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setExecutionToDelete(selectedExecution)}>
                          <Trash2 size={14} className="mr-2" />
                          Delete
                      </DropdownMenuItem>
                  </DropdownMenuContent>
              </DropdownMenu>,
          ]
        : undefined;

    return (
        <div className="flex h-full flex-col">
            <Header title={headerTitle} breadcrumbs={breadcrumbs} buttons={headerButtons} />

            <div className="flex min-h-0 flex-1">
                <ConfigurationSidebar
                    task={task}
                    execution={displayedExecution}
                    isReadOnly={!!selectedExecution}
                    onEdit={() => onEdit(task)}
                    onRunNow={() => runNowMutation.mutate(task.id)}
                    onToggleEnabled={() => (task.enabled ? disableMutation.mutate(task.id) : enableMutation.mutate(task.id))}
                    onDelete={() => onDelete(task.id, task.name)}
                    isRunNowPending={runNowMutation.isPending}
                />

                <main className="flex-1 space-y-8 overflow-y-auto px-8 py-6">
                    {selectedExecution ? (
                        <ExecutionDetailPanel execution={selectedExecution} activeTab={detailTab} onTabChange={setDetailTab} />
                    ) : (
                        <>
                            <LatestExecutionPanel execution={latestExecution} onGoToChat={handleGoToChat} />
                            <div id="execution-history-anchor" />
                            <ExecutionHistoryTable
                                executions={executions}
                                totalCount={totalCount}
                                page={page}
                                onPageChange={setPage}
                                onRowClick={handleSelectExecution}
                                isLoading={isLoading}
                                onDeleteExecution={setExecutionToDelete}
                                filterFrom={filterFrom}
                                filterTo={filterTo}
                                onFilterFromChange={handleFilterFromChange}
                                onFilterToChange={handleFilterToChange}
                            />
                        </>
                    )}
                </main>
            </div>

            <ConfirmationDialog
                open={!!executionToDelete}
                onOpenChange={open => {
                    if (!open) setExecutionToDelete(null);
                }}
                title={executionToDelete ? `Delete ${formatExecutionLabel(executionToDelete)}` : ""}
                content={
                    executionToDelete ? (
                        <p className="text-sm">
                            Deleting <strong>{formatExecutionLabel(executionToDelete)}</strong> will remove it from the <strong>{task.name}</strong> execution history and will no longer be available to view.
                        </p>
                    ) : null
                }
                actionLabels={{ confirm: "Delete" }}
                isLoading={deleteExecutionMutation.isPending}
                onConfirm={async () => {
                    if (!executionToDelete) return;
                    const deletedId = executionToDelete.id;
                    await deleteExecutionMutation.mutateAsync(deletedId);
                    setExecutionToDelete(null);
                    if (selectedExecutionId === deletedId) {
                        handleClearSelection();
                    }
                }}
            />
        </div>
    );
};
