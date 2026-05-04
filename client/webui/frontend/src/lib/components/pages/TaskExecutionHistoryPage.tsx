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
import { ChevronLeft, ChevronRight, Loader2, MoreHorizontal, Pencil, Play, Pause, Trash2, Zap, MessageSquare } from "lucide-react";
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
    PaginationEllipsis,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    DatePicker,
} from "@/lib/components/ui";
import { ExecutionArtifactsView, ExecutionInlineArtifacts } from "@/lib/components/scheduled-tasks/ExecutionArtifactsView";
import { MarkdownWrapper } from "@/lib/components";
import { useChatContext, useAgentCards } from "@/lib/hooks";
import { useTaskExecutions, useRunScheduledTaskNow, useEnableScheduledTask, useDisableScheduledTask, useDeleteExecution, useExecutionArtifacts } from "@/lib/api/scheduled-tasks";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import { formatDuration, formatEpochTimestampShort } from "@/lib/utils/format";
import { paginationPages } from "@/lib/utils/pagination";
import { cn } from "@/lib/utils";
import { formatSchedule } from "@/lib/components/scheduled-tasks/utils";
import { getStatusBadge } from "@/lib/components/scheduled-tasks/ExecutionList";

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

const PAGE_SIZE = 10;
const IN_PROGRESS_STATUSES: ReadonlySet<TaskExecution["status"]> = new Set(["pending", "running"]);

/** Display name for an execution — its scheduled time formatted as
 *  "YYYY-MM-DD HH:MM:SS". Falls back to the ID prefix when no scheduled
 *  timestamp is available. */
function executionDisplayName(ex: TaskExecution): string {
    if (ex.scheduledFor) return formatEpochTimestampShort(ex.scheduledFor);
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
    execution: TaskExecution | null;
    onEdit: () => void;
    onRunNow: () => void;
    onToggleEnabled: () => void;
    onDelete: () => void;
    isRunNowPending: boolean;
}> = ({ task, execution, onEdit, onRunNow, onToggleEnabled, onDelete, isRunNowPending }) => {
    const canRunNow = task.scheduleType !== "one_time" && task.source !== "config";
    const { agentNameMap } = useAgentCards();
    // Prefer the per-execution snapshot so the sidebar reflects the config
    // that produced this run, even if the task has since been edited.
    // Falls back to the live task for executions that ran before snapshots
    // were captured.
    const snapshot = execution?.taskSnapshot ?? null;
    const name = snapshot?.name ?? task.name;
    const description = snapshot?.description ?? task.description;
    const scheduleType = snapshot?.scheduleType ?? task.scheduleType;
    const scheduleExpression = snapshot?.scheduleExpression ?? task.scheduleExpression;
    const timezone = snapshot?.timezone ?? task.timezone;
    const targetAgentName = snapshot?.targetAgentName ?? task.targetAgentName;
    const targetType = snapshot?.targetType ?? task.targetType;
    const taskMessage = snapshot?.taskMessage ?? task.taskMessage;
    const agentDisplay = agentNameMap[targetAgentName] || targetAgentName;
    const taskMessageText = taskMessage?.[0]?.text || "";

    return (
        <aside className="flex h-full w-[320px] flex-col overflow-y-auto border-r bg-(--background-w10)">
            <div className="flex items-center justify-between px-6 py-4">
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
                <ConfigField label="Name">{name}</ConfigField>
                <ConfigField label="Description" multiline>
                    {description || <span className="text-(--secondary-text-wMain) italic">No description</span>}
                </ConfigField>
                <ConfigField label="Schedule">{formatSchedule({ scheduleType, scheduleExpression })}</ConfigField>
                <ConfigField label="Timezone">{timezone}</ConfigField>
                <ConfigField label={targetType === "workflow" ? "Workflow" : "Agent"}>
                    <span className="text-(--primary-text-wMain)">{agentDisplay}</span>
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

/**
 * Render the agent's response inside a scrollable bordered box. The Latest
 * Execution panel uses the truncated snippet from result_summary.agent_response;
 * the per-execution detail page passes `full=true` to render the untruncated
 * agent_response_full instead.
 */
const renderOutput = (execution: TaskExecution, full: boolean) => {
    const text = full ? execution.resultSummary?.agentResponseFull || execution.resultSummary?.agentResponse : execution.resultSummary?.agentResponse;
    const fallback = execution.resultSummary?.messages?.find(m => m.role === "agent")?.text || "";
    const content = text || fallback;
    return (
        <div className="max-h-[16rem] overflow-y-auto rounded-md border bg-(--background-w10) p-4 text-sm break-words">
            {content ? (
                <MarkdownWrapper content={content} className="text-sm" />
            ) : execution.errorMessage ? (
                <span className="whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</span>
            ) : (
                <span className="text-(--secondary-text-wMain) italic">No output yet.</span>
            )}
        </div>
    );
};

const LatestExecutionPanel: React.FC<{
    execution: TaskExecution | null;
    onGoToChat: (executionId: string) => void;
}> = ({ execution, onGoToChat }) => {
    if (!execution) {
        return <div className="rounded-md border bg-(--background-w10) p-6 text-sm text-(--secondary-text-wMain) italic">No executions yet.</div>;
    }

    const isInFlight = IN_PROGRESS_STATUSES.has(execution.status);
    const completedAt = execution.completedAt ? formatEpochTimestampShort(execution.completedAt) : "—";
    const duration = execution.durationMs ? formatDuration(execution.durationMs) : "—";

    return (
        <section className="space-y-4">
            <div className="-mt-6 -ml-8 flex items-start justify-between gap-8 border-b py-3 pl-8">
                <div className="min-w-0 flex-shrink-0">
                    <div className="text-xs text-(--secondary-text-wMain)">Latest Execution</div>
                    <div className="truncate text-base font-semibold" title={executionDisplayName(execution)}>
                        {executionDisplayName(execution)}
                    </div>
                </div>
                <div className="flex flex-1 items-center gap-8">
                    <Metric label="Status">{getStatusBadge(execution.status)}</Metric>
                    <Metric label="Completed On">{completedAt}</Metric>
                    <Metric label="Duration">{isInFlight ? <Loader2 className="h-4 w-4 animate-spin text-(--brand-wMain)" /> : duration}</Metric>
                </div>
                <Button onClick={() => onGoToChat(execution.id)} disabled={isInFlight && !execution.startedAt}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    View Chat Output
                </Button>
            </div>

            <div>
                <div className="mb-2 text-sm font-semibold">Output Summary</div>
                {renderOutput(execution, false)}
            </div>
        </section>
    );
};

const ExecutionDetailPanel: React.FC<{
    execution: TaskExecution;
    activeTab: "output" | "artifacts";
    onTabChange: (tab: "output" | "artifacts") => void;
}> = ({ execution, activeTab, onTabChange }) => {
    const { data: artifacts } = useExecutionArtifacts(execution.id);
    const hasArtifacts = (artifacts?.length ?? 0) > 0;

    const isInFlight = IN_PROGRESS_STATUSES.has(execution.status);
    const startedAt = execution.startedAt ? formatEpochTimestampShort(execution.startedAt) : "—";
    const completedAt = execution.completedAt ? formatEpochTimestampShort(execution.completedAt) : "—";
    const duration = execution.durationMs ? formatDuration(execution.durationMs) : "—";

    const metrics = (
        <>
            <Metric label="Status">{getStatusBadge(execution.status)}</Metric>
            <Metric label="Started On">{startedAt}</Metric>
            <Metric label="Completed On">{completedAt}</Metric>
            <Metric label="Duration">{isInFlight ? <Loader2 className="h-4 w-4 animate-spin text-(--brand-wMain)" /> : duration}</Metric>
        </>
    );

    const fullText = execution.resultSummary?.agentResponseFull || execution.resultSummary?.agentResponse || execution.resultSummary?.messages?.find(m => m.role === "agent")?.text || "";

    const outputBody = (
        <div className="space-y-4 text-sm break-words">
            {fullText ? (
                <MarkdownWrapper content={fullText} className="text-sm" />
            ) : execution.errorMessage ? (
                <div className="whitespace-pre-wrap text-(--error-wMain)">{execution.errorMessage}</div>
            ) : (
                <div className="text-(--secondary-text-wMain) italic">No output yet.</div>
            )}
            {hasArtifacts && <ExecutionInlineArtifacts executionId={execution.id} />}
        </div>
    );

    return (
        <section className="space-y-4">
            {hasArtifacts ? (
                <>
                    <div className="-mt-6 -ml-8 flex items-center gap-8 border-b py-3 pl-8">
                        <div className="flex items-center overflow-hidden rounded-lg border">
                            <button type="button" onClick={() => onTabChange("output")} className={cn("border-r px-4 py-2 hover:bg-(--secondary-w20)", activeTab === "output" && "rounded-l-lg bg-(--primary-w20)")}>
                                Output
                            </button>
                            <button type="button" onClick={() => onTabChange("artifacts")} className={cn("px-4 py-2 hover:bg-(--secondary-w20)", activeTab === "artifacts" && "rounded-r-lg bg-(--primary-w20)")}>
                                Artifacts
                            </button>
                        </div>
                        <div className="flex flex-1 items-center gap-8">{metrics}</div>
                    </div>
                    <div className="mt-4">{activeTab === "output" ? outputBody : <ExecutionArtifactsView executionId={execution.id} />}</div>
                </>
            ) : (
                <>
                    <div className="-mt-6 -ml-8 flex items-center gap-8 border-b py-3 pl-8">
                        <div className="flex flex-1 items-center gap-8">{metrics}</div>
                    </div>
                    {outputBody}
                </>
            )}
        </section>
    );
};

// ─── Execution history table ──────────────────────────────────────────────

const ExecutionHistoryTable: React.FC<{
    executions: TaskExecution[];
    totalCount: number;
    page: number;
    onPageChange: (p: number) => void;
    onRowClick: (executionId: string) => void;
    isLoading: boolean;
    onDeleteExecution: (execution: TaskExecution) => void;
    filterFrom: string;
    filterTo: string;
    onFilterFromChange: (value: string) => void;
    onFilterToChange: (value: string) => void;
}> = ({ executions, totalCount, page, onPageChange, onRowClick, isLoading, onDeleteExecution, filterFrom, filterTo, onFilterFromChange, onFilterToChange }) => {
    // Column sort is intentionally not exposed: the table is server-paginated,
    // so sorting only the current page would mislead users into thinking they
    // were seeing the global top-N by their chosen sort. Server-side sort can
    // be added later if/when a sort param is plumbed through the API.
    const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
    const showingFrom = totalCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
    const showingTo = Math.min(page * PAGE_SIZE, totalCount);

    const hasFilter = !!(filterFrom || filterTo);

    return (
        <section>
            <h3 className="mb-3 text-base font-semibold">Execution History</h3>

            <div className="mb-3 flex items-center gap-2">
                <span className="text-xs text-(--secondary-text-wMain)">Date Range</span>
                <DatePicker value={filterFrom} onChange={onFilterFromChange} placeholder="YYYY-MM-DD" className={cn("w-48", filterFrom && "text-(--primary-text-wMain)")} />
                <span className="text-sm text-(--secondary-text-wMain)">to</span>
                <DatePicker value={filterTo} onChange={onFilterToChange} min={filterFrom || undefined} placeholder="YYYY-MM-DD" className={cn("w-48", filterTo && "text-(--primary-text-wMain)")} />
                {hasFilter && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                            onFilterFromChange("");
                            onFilterToChange("");
                        }}
                    >
                        Clear
                    </Button>
                )}
            </div>

            <div className="overflow-hidden rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="px-4 font-semibold">Completed On</TableHead>
                            <TableHead className="px-4 font-semibold">Status</TableHead>
                            <TableHead className="px-4 font-semibold">Duration</TableHead>
                            <TableHead className="w-10" />
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading && executions.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={4} className="py-8 text-center text-sm text-(--secondary-text-wMain)">
                                    <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                                </TableCell>
                            </TableRow>
                        ) : executions.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={4} className="py-8 text-center text-sm text-(--secondary-text-wMain) italic">
                                    No executions yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            executions.map(ex => {
                                const isInFlight = IN_PROGRESS_STATUSES.has(ex.status);
                                return (
                                    <TableRow key={ex.id} className="hover:bg-(--secondary-w10)">
                                        <TableCell className="px-4">
                                            <Button variant="link" className="h-auto p-0" onClick={() => onRowClick(ex.id)}>
                                                {formatExecutionLabel(ex)}
                                            </Button>
                                        </TableCell>
                                        <TableCell className="px-4">
                                            {isInFlight ? (
                                                <span className="inline-flex items-center gap-1.5 text-sm text-(--primary-text-wMain)">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin text-(--brand-wMain)" />
                                                    {ex.status === "pending" ? "Pending" : "In progress"}
                                                </span>
                                            ) : (
                                                getStatusBadge(ex.status)
                                            )}
                                        </TableCell>
                                        <TableCell className="px-4">{ex.durationMs ? formatDurationVerbose(ex.durationMs) : "—"}</TableCell>
                                        <TableCell className="w-10" onClick={e => e.stopPropagation()}>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" tooltip="Actions">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => onDeleteExecution(ex)}>
                                                        <Trash2 size={14} className="mr-2" />
                                                        Delete
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

            {/* Pagination footer — pagination visually centered with the
                results count absolutely positioned right so the centered
                pagination stays centered regardless of the count's width.
                Mirrors the ellipsis logic from common/PaginationControls
                but uses chevron-only prev/next to match the design. */}
            {totalCount > 0 && (
                <div className="relative mt-3 flex items-center justify-center">
                    <Pagination>
                        <PaginationContent>
                            <PaginationItem>
                                <PaginationLink aria-label="Go to previous page" onClick={() => page > 1 && onPageChange(page - 1)} className={page <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}>
                                    <ChevronLeft className="h-4 w-4" />
                                </PaginationLink>
                            </PaginationItem>
                            {paginationPages(page, totalPages).map((p, i) => (
                                <PaginationItem key={i}>
                                    {p === "ellipsis" ? (
                                        <PaginationEllipsis />
                                    ) : (
                                        <PaginationLink isActive={p === page} onClick={() => onPageChange(p)} className="cursor-pointer">
                                            {p}
                                        </PaginationLink>
                                    )}
                                </PaginationItem>
                            ))}
                            <PaginationItem>
                                <PaginationLink aria-label="Go to next page" onClick={() => page < totalPages && onPageChange(page + 1)} className={page >= totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}>
                                    <ChevronRight className="h-4 w-4" />
                                </PaginationLink>
                            </PaginationItem>
                        </PaginationContent>
                    </Pagination>
                    <span className="absolute top-1/2 right-2 -translate-y-1/2 text-xs text-(--secondary-text-wMain)">
                        Showing {showingFrom}-{showingTo} of {totalCount} results
                    </span>
                </div>
            )}
        </section>
    );
};

const formatExecutionLabel = (ex: TaskExecution): string => {
    const ts = ex.completedAt ?? ex.startedAt ?? ex.scheduledFor;
    return ts ? formatEpochTimestampShort(ts) : "—";
};

// ─── Page ─────────────────────────────────────────────────────────────────

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

    const { data, isLoading, refetch } = useTaskExecutions(task.id, page, PAGE_SIZE, filterFromMs, filterToMs);
    const executions = data?.executions ?? [];
    const totalCount = data?.total ?? executions.length;

    // The "Latest Execution" panel and the Configuration sidebar's snapshot
    // must reflect the actual most recent run, independent of the table's
    // current page or date filter. Fetch page 1, size 1, unfiltered.
    const { data: latestData, refetch: refetchLatest } = useTaskExecutions(task.id, 1, 1, null, null);
    const latestExecutionFromQuery = latestData?.executions?.[0] ?? null;

    const runNowMutation = useRunScheduledTaskNow();
    const enableMutation = useEnableScheduledTask();
    const disableMutation = useDisableScheduledTask();
    const deleteExecutionMutation = useDeleteExecution(task.id);
    const [executionToDelete, setExecutionToDelete] = useState<TaskExecution | null>(null);
    // Stash the row alongside its id so the detail panel survives smart-poll
    // refetches that push the row to another page (or out of the current
    // date filter).
    const [stashedSelectedExecution, setStashedSelectedExecution] = useState<TaskExecution | null>(null);
    const selectedExecutionId = stashedSelectedExecution?.id ?? null;
    const handleSelectExecution = (executionId: string) => {
        const row = executions.find(e => e.id === executionId) ?? null;
        if (row) setStashedSelectedExecution(row);
    };
    const [detailTab, setDetailTab] = useState<"output" | "artifacts">("output");

    // Smart polling — fast while a run is in flight, slow otherwise. Mirrors
    // the previous page's behavior so users see live updates without a refresh.
    const hasActive = executions.some(e => IN_PROGRESS_STATUSES.has(e.status)) || (latestExecutionFromQuery ? IN_PROGRESS_STATUSES.has(latestExecutionFromQuery.status) : false);
    React.useEffect(() => {
        let timerId: ReturnType<typeof setTimeout>;
        const tick = () => {
            if (!document.hidden) {
                refetch();
                refetchLatest();
            }
            timerId = setTimeout(tick, hasActive ? 5_000 : 30_000);
        };
        timerId = setTimeout(tick, hasActive ? 5_000 : 30_000);
        const onVis = () => {
            if (!document.hidden) {
                refetch();
                refetchLatest();
            }
        };
        document.addEventListener("visibilitychange", onVis);
        return () => {
            clearTimeout(timerId);
            document.removeEventListener("visibilitychange", onVis);
        };
    }, [refetch, refetchLatest, hasActive]);

    const latestExecution = latestExecutionFromQuery;
    // Prefer the freshest copy of the selected row from either the current
    // page or the latest-execution query (so live updates flow through), and
    // fall back to the stashed copy when neither query contains it any more.
    const selectedExecution = selectedExecutionId ? (executions.find(e => e.id === selectedExecutionId) ?? (latestExecutionFromQuery?.id === selectedExecutionId ? latestExecutionFromQuery : null) ?? stashedSelectedExecution) : null;
    // The Configuration sidebar reflects the currently-displayed execution's
    // snapshot — latest by default, or the row the user opened.
    const displayedExecution = selectedExecution ?? latestExecution;

    const handleGoToChat = async (executionId: string) => {
        await handleSwitchSession(`scheduled_${executionId}`);
        navigate("/chat");
    };

    const breadcrumbs = selectedExecution
        ? [{ label: "Scheduled Tasks", onClick: onBack }, { label: task.name, onClick: () => setStashedSelectedExecution(null) }, { label: formatExecutionLabel(selectedExecution) }]
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
                        setStashedSelectedExecution(null);
                    }
                }}
            />
        </div>
    );
};
