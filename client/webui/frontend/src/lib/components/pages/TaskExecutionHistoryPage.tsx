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

import React, { useMemo, useState } from "react";
import { Loader2, MoreHorizontal, Pencil, Play, Pause, Trash2, Zap, MessageSquare } from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { ScheduledTask, TaskExecution } from "@/lib/types/scheduled-tasks";
import { Header } from "@/lib/components/header";
import {
    Button,
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    Pagination,
    PaginationContent,
    PaginationItem,
    PaginationLink,
    PaginationNext,
    PaginationPrevious,
    Table,
    TableBody,
    TableCell,
    TableHeader,
    TableRow,
    SortableTableHead,
} from "@/lib/components/ui";
import { MarkdownWrapper } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";
import { useTaskExecutions, useRunScheduledTaskNow, useEnableScheduledTask, useDisableScheduledTask } from "@/lib/api/scheduled-tasks";
import { formatDuration } from "@/lib/utils/format";

// "YYYY-MM-DD HH:MM:SS" in the user's local timezone — matches the executions
// page mock. Auto-detects whether the timestamp is in seconds or milliseconds.
const pad = (n: number) => String(n).padStart(2, "0");
function formatExecutionTimestamp(ts: number): string {
    const d = new Date(ts < 10_000_000_000 ? ts * 1000 : ts);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// Spell out a duration with the two largest non-zero units, properly pluralized
// (e.g. "30 seconds", "1 minute", "2 hours 5 minutes"). Used in the history
// table where the verbose form reads more naturally than "30s" or "2h 5m".
function formatDurationVerbose(ms: number): string {
    if (ms < 0 || !isFinite(ms)) return "—";
    if (ms < 1000) return `${Math.round(ms)} ms`;
    const totalSeconds = Math.round(ms / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const parts: string[] = [];
    const push = (n: number, unit: string) => {
        if (n > 0) parts.push(`${n} ${unit}${n === 1 ? "" : "s"}`);
    };
    push(days, "day");
    push(hours, "hour");
    push(minutes, "minute");
    push(seconds, "second");
    if (parts.length === 0) return "0 seconds";
    return parts.slice(0, 2).join(" ");
}
import { formatSchedule } from "@/lib/components/scheduled-tasks/utils";
import { getStatusBadge } from "@/lib/components/scheduled-tasks/ExecutionList";
import { useAgentCards } from "@/lib/hooks";

const PAGE_SIZE = 20;
const IN_PROGRESS_STATUSES: ReadonlySet<TaskExecution["status"]> = new Set(["pending", "running"]);

/** Display name for an execution — its scheduled time formatted as
 *  "YYYY-MM-DD HH:MM:SS". Falls back to the ID prefix when no scheduled
 *  timestamp is available. */
function executionDisplayName(ex: TaskExecution): string {
    if (ex.scheduledFor) return formatExecutionTimestamp(ex.scheduledFor);
    return ex.id.slice(0, 8);
}

interface TaskExecutionHistoryPageProps {
    task: ScheduledTask;
    onBack: () => void;
    onEdit: (task: ScheduledTask) => void;
    onDelete: (id: string, name: string) => void;
}

// ─── Configuration sidebar ────────────────────────────────────────────────

const ConfigField: React.FC<{ label: string; children: React.ReactNode; multiline?: boolean }> = ({ label, children, multiline }) => (
    <div className="space-y-1">
        <div className="text-xs text-(--secondary-text-wMain)">{label}</div>
        <div className={multiline ? "text-sm break-words whitespace-pre-wrap" : "truncate text-sm"}>{children}</div>
    </div>
);

const ConfigurationSidebar: React.FC<{
    task: ScheduledTask;
    onEdit: () => void;
    onRunNow: () => void;
    onViewHistory: () => void;
    onToggleEnabled: () => void;
    onDelete: () => void;
    isRunNowPending: boolean;
}> = ({ task, onEdit, onRunNow, onToggleEnabled, onDelete, isRunNowPending }) => {
    const { agentNameMap } = useAgentCards();
    const agentDisplay = agentNameMap[task.targetAgentName] || task.targetAgentName;
    const taskMessageText = task.taskMessage?.[0]?.text || "";
    const canRunNow = task.scheduleType !== "one_time" && task.source !== "config";

    return (
        <aside className="flex h-full w-[320px] flex-col overflow-y-auto border-r bg-(--background-w10)">
            <div className="flex items-center justify-between border-b px-6 py-4">
                <h2 className="text-base font-semibold">Configuration</h2>
                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={onEdit} className="h-8 px-2">
                        <Pencil className="mr-1 h-3.5 w-3.5" />
                        Edit
                    </Button>
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" tooltip="Actions">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            {/* Edit lives on the dedicated button next to this menu, and
                                "View Execution History" is redundant on this page — the
                                menu intentionally only carries Run Now / Pause-Resume /
                                Delete to match the redesigned config section. */}
                            {canRunNow && (
                                <DropdownMenuItem onSelect={onRunNow} disabled={isRunNowPending}>
                                    <Zap size={14} className="mr-2" />
                                    {isRunNowPending ? "Running…" : "Run Now"}
                                </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onClick={onToggleEnabled}>
                                {task.enabled ? (
                                    <>
                                        <Pause size={14} className="mr-2" />
                                        Pause Task
                                    </>
                                ) : (
                                    <>
                                        <Play size={14} className="mr-2" />
                                        Resume Task
                                    </>
                                )}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={onDelete}>
                                <Trash2 size={14} className="mr-2" />
                                Delete
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            <div className="space-y-5 px-6 py-5">
                <ConfigField label="Name">{task.name}</ConfigField>
                <ConfigField label="Description" multiline>
                    {task.description || <span className="text-(--secondary-text-wMain) italic">No description</span>}
                </ConfigField>
                <ConfigField label="Schedule">{formatSchedule(task)}</ConfigField>
                <ConfigField label="Timezone">{task.timezone}</ConfigField>
                <ConfigField label={task.targetType === "workflow" ? "Workflow" : "Agent"}>
                    <span className="text-(--info-wMain)">{agentDisplay}</span>
                </ConfigField>
                <ConfigField label="Output">Chat</ConfigField>
                <ConfigField label="Instructions" multiline>
                    {taskMessageText || <span className="text-(--secondary-text-wMain) italic">No instructions</span>}
                </ConfigField>
            </div>
        </aside>
    );
};

// ─── Latest execution panel ───────────────────────────────────────────────

const Metric: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
    <div>
        <div className="mb-1 text-xs text-(--secondary-text-wMain)">{label}</div>
        <div className="text-sm">{children}</div>
    </div>
);

const LatestExecutionPanel: React.FC<{ execution: TaskExecution | null; onGoToChat: (executionId: string) => void }> = ({ execution, onGoToChat }) => {
    if (!execution) {
        return <div className="rounded-md border bg-(--background-w10) p-6 text-sm text-(--secondary-text-wMain) italic">No executions yet.</div>;
    }

    const isInFlight = IN_PROGRESS_STATUSES.has(execution.status);
    const completedAt = execution.completedAt ? formatExecutionTimestamp(execution.completedAt) : "—";
    const duration = execution.durationMs ? formatDuration(execution.durationMs) : "—";
    const summary = execution.resultSummary?.agentResponse || execution.resultSummary?.messages?.find(m => m.role === "agent")?.text || "";

    return (
        <section className="space-y-4">
            <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                    <div className="text-xs text-(--secondary-text-wMain)">Latest Execution</div>
                    <h3 className="truncate text-lg font-semibold" title={executionDisplayName(execution)}>
                        {executionDisplayName(execution)}
                    </h3>
                </div>
                <Button onClick={() => onGoToChat(execution.id)} disabled={isInFlight && !execution.startedAt}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    View Chat Output
                </Button>
            </div>

            <div className="grid grid-cols-3 gap-6 border-y py-4">
                <Metric label="Status">{getStatusBadge(execution.status)}</Metric>
                <Metric label="Completed On">{completedAt}</Metric>
                <Metric label="Duration">{isInFlight ? <Loader2 className="h-4 w-4 animate-spin text-(--brand-wMain)" /> : duration}</Metric>
            </div>

            <div>
                <div className="mb-2 text-sm font-semibold">Output Summary</div>
                {/* The output box scrolls internally so a long agent response
                    doesn't push the Execution History table off the page.
                    Renders markdown so headings/lists/code from the agent
                    response come through formatted. */}
                <div className="max-h-[16rem] overflow-y-auto rounded-md border bg-(--background-w10) p-4 text-sm break-words">
                    {summary ? (
                        <MarkdownWrapper content={summary} className="text-sm" />
                    ) : execution.errorMessage ? (
                        <span className="whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</span>
                    ) : (
                        <span className="text-(--secondary-text-wMain) italic">No output yet.</span>
                    )}
                </div>
            </div>
        </section>
    );
};

// ─── Execution history table ──────────────────────────────────────────────

type SortKey = "name" | "status" | "duration" | "completedOn";
type SortDir = "asc" | "desc";

const ExecutionHistoryTable: React.FC<{
    executions: TaskExecution[];
    totalCount: number;
    page: number;
    onPageChange: (p: number) => void;
    onRowClick: (executionId: string) => void;
    isLoading: boolean;
}> = ({ executions, totalCount, page, onPageChange, onRowClick, isLoading }) => {
    const [sortKey, setSortKey] = useState<SortKey>("completedOn");
    const [sortDir, setSortDir] = useState<SortDir>("desc");

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDir(d => (d === "asc" ? "desc" : "asc"));
        } else {
            setSortKey(key);
            setSortDir("desc");
        }
    };

    // Sort applies to the current page only (server provides pagination).
    const sorted = useMemo(() => {
        const arr = [...executions];
        const dirMul = sortDir === "asc" ? 1 : -1;
        arr.sort((a, b) => {
            const av = (() => {
                switch (sortKey) {
                    case "name":
                        return executionDisplayName(a).toLowerCase();
                    case "status":
                        return a.status;
                    case "duration":
                        return a.durationMs ?? -1;
                    case "completedOn":
                        return a.completedAt ?? a.startedAt ?? a.scheduledFor ?? 0;
                }
            })();
            const bv = (() => {
                switch (sortKey) {
                    case "name":
                        return executionDisplayName(b).toLowerCase();
                    case "status":
                        return b.status;
                    case "duration":
                        return b.durationMs ?? -1;
                    case "completedOn":
                        return b.completedAt ?? b.startedAt ?? b.scheduledFor ?? 0;
                }
            })();
            if (av < bv) return -1 * dirMul;
            if (av > bv) return 1 * dirMul;
            return 0;
        });
        return arr;
    }, [executions, sortKey, sortDir]);

    const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
    const showingFrom = totalCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
    const showingTo = Math.min(page * PAGE_SIZE, totalCount);

    return (
        <section>
            <h3 className="mb-3 text-base font-semibold">Execution History</h3>

            <div className="overflow-hidden rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <SortableTableHead column="name" currentSortKey={sortKey} sortDir={sortDir} onSort={k => handleSort(k as SortKey)}>
                                Name
                            </SortableTableHead>
                            <SortableTableHead column="status" currentSortKey={sortKey} sortDir={sortDir} onSort={k => handleSort(k as SortKey)}>
                                Status
                            </SortableTableHead>
                            <SortableTableHead column="duration" currentSortKey={sortKey} sortDir={sortDir} onSort={k => handleSort(k as SortKey)}>
                                Duration
                            </SortableTableHead>
                            <SortableTableHead column="completedOn" currentSortKey={sortKey} sortDir={sortDir} onSort={k => handleSort(k as SortKey)}>
                                Completed On
                            </SortableTableHead>
                            <th className="w-10" />
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading && executions.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={5} className="py-8 text-center text-sm text-(--secondary-text-wMain)">
                                    <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                                </TableCell>
                            </TableRow>
                        ) : sorted.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={5} className="py-8 text-center text-sm text-(--secondary-text-wMain) italic">
                                    No executions yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            sorted.map(ex => {
                                const isInFlight = IN_PROGRESS_STATUSES.has(ex.status);
                                return (
                                    <TableRow key={ex.id} className="cursor-pointer hover:bg-(--secondary-w10)" onClick={() => onRowClick(ex.id)}>
                                        <TableCell className="font-medium">{executionDisplayName(ex)}</TableCell>
                                        <TableCell>
                                            {isInFlight ? (
                                                <span className="inline-flex items-center gap-1.5 text-sm text-(--brand-wMain)">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    {ex.status === "pending" ? "Pending" : "In progress"}
                                                </span>
                                            ) : (
                                                getStatusBadge(ex.status)
                                            )}
                                        </TableCell>
                                        <TableCell>{ex.durationMs ? formatDurationVerbose(ex.durationMs) : "—"}</TableCell>
                                        <TableCell>{ex.completedAt ? formatExecutionTimestamp(ex.completedAt) : "—"}</TableCell>
                                        <TableCell className="w-10" onClick={e => e.stopPropagation()}>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" tooltip="Actions">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => onRowClick(ex.id)}>
                                                        <MessageSquare size={14} className="mr-2" />
                                                        View Chat Output
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination footer */}
            <div className="mt-3 flex items-center justify-between text-xs text-(--secondary-text-wMain)">
                <Pagination className="mx-0 justify-start">
                    <PaginationContent>
                        <PaginationItem>
                            <PaginationPrevious
                                onClick={e => {
                                    e.preventDefault();
                                    if (page > 1) onPageChange(page - 1);
                                }}
                                aria-disabled={page <= 1}
                                className={page <= 1 ? "pointer-events-none opacity-50" : ""}
                            />
                        </PaginationItem>
                        {Array.from({ length: totalPages }).map((_, i) => {
                            const p = i + 1;
                            // Compact display: show first, last, current, neighbors; collapse the rest.
                            if (totalPages > 7 && p !== 1 && p !== totalPages && Math.abs(p - page) > 1) return null;
                            return (
                                <PaginationItem key={p}>
                                    <PaginationLink
                                        isActive={p === page}
                                        onClick={e => {
                                            e.preventDefault();
                                            onPageChange(p);
                                        }}
                                    >
                                        {p}
                                    </PaginationLink>
                                </PaginationItem>
                            );
                        })}
                        <PaginationItem>
                            <PaginationNext
                                onClick={e => {
                                    e.preventDefault();
                                    if (page < totalPages) onPageChange(page + 1);
                                }}
                                aria-disabled={page >= totalPages}
                                className={page >= totalPages ? "pointer-events-none opacity-50" : ""}
                            />
                        </PaginationItem>
                    </PaginationContent>
                </Pagination>
                <span>
                    Showing {showingFrom}-{showingTo} of {totalCount} results
                </span>
            </div>
        </section>
    );
};

// ─── Page ─────────────────────────────────────────────────────────────────

export const TaskExecutionHistoryPage: React.FC<TaskExecutionHistoryPageProps> = ({ task, onBack, onEdit, onDelete }) => {
    const navigate = useNavigate();
    const { handleSwitchSession } = useChatContext();
    const [page, setPage] = useState(1);

    const { data, isLoading, refetch } = useTaskExecutions(task.id, page, PAGE_SIZE);
    const executions = data?.executions ?? [];
    const totalCount = data?.total ?? executions.length;

    const runNowMutation = useRunScheduledTaskNow();
    const enableMutation = useEnableScheduledTask();
    const disableMutation = useDisableScheduledTask();

    // Smart polling — fast while a run is in flight, slow otherwise. Mirrors
    // the previous page's behavior so users see live updates without a refresh.
    const hasActive = executions.some(e => IN_PROGRESS_STATUSES.has(e.status));
    React.useEffect(() => {
        let timerId: ReturnType<typeof setTimeout>;
        const tick = () => {
            if (!document.hidden) refetch();
            timerId = setTimeout(tick, hasActive ? 5_000 : 30_000);
        };
        timerId = setTimeout(tick, hasActive ? 5_000 : 30_000);
        const onVis = () => {
            if (!document.hidden) refetch();
        };
        document.addEventListener("visibilitychange", onVis);
        return () => {
            clearTimeout(timerId);
            document.removeEventListener("visibilitychange", onVis);
        };
    }, [refetch, hasActive]);

    const latestExecution = executions[0] ?? null;

    const handleGoToChat = async (executionId: string) => {
        await handleSwitchSession(`scheduled_${executionId}`);
        navigate("/chat");
    };

    return (
        <div className="flex h-full flex-col">
            <Header title={task.name} breadcrumbs={[{ label: "Scheduled Tasks", onClick: onBack }, { label: task.name }]} />

            <div className="flex min-h-0 flex-1">
                <ConfigurationSidebar
                    task={task}
                    onEdit={() => onEdit(task)}
                    onRunNow={() => runNowMutation.mutate(task.id)}
                    onViewHistory={() => {
                        // Already on the history page — scroll to the table for clarity.
                        document.getElementById("execution-history-anchor")?.scrollIntoView({ behavior: "smooth" });
                    }}
                    onToggleEnabled={() => (task.enabled ? disableMutation.mutate(task.id) : enableMutation.mutate(task.id))}
                    onDelete={() => onDelete(task.id, task.name)}
                    isRunNowPending={runNowMutation.isPending}
                />

                <main className="flex-1 space-y-8 overflow-y-auto px-8 py-6">
                    <LatestExecutionPanel execution={latestExecution} onGoToChat={handleGoToChat} />

                    <div id="execution-history-anchor" />
                    <ExecutionHistoryTable executions={executions} totalCount={totalCount} page={page} onPageChange={setPage} onRowClick={handleGoToChat} isLoading={isLoading} />
                </main>
            </div>
        </div>
    );
};
