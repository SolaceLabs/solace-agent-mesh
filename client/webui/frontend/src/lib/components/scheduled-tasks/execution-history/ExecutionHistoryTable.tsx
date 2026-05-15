import React from "react";
import { Loader2, MoreHorizontal, Trash2 } from "lucide-react";

import type { TaskExecution } from "@/lib/types/scheduled-tasks";
import { Button, DatePicker, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui";
import { PaginationControls } from "@/lib/components/common/PaginationControls";
import { cn } from "@/lib/utils";
import { getStatusBadge, IN_PROGRESS_STATUSES } from "@/lib/components/scheduled-tasks/StatusBadge";
import { PAGE_SIZE, formatDurationVerbose, formatExecutionLabel } from "./helpers";

interface ExecutionHistoryTableProps {
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
}

export const ExecutionHistoryTable: React.FC<ExecutionHistoryTableProps> = ({ executions, totalCount, page, onPageChange, onRowClick, isLoading, onDeleteExecution, filterFrom, filterTo, onFilterFromChange, onFilterToChange }) => {
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
                        <TableRow className="hover:bg-transparent">
                            <TableHead className="px-4 font-semibold">Run Time</TableHead>
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

            {totalCount > 0 && (
                <PaginationControls
                    variant="compact"
                    totalPages={totalPages}
                    currentPage={page}
                    onPageChange={onPageChange}
                    summary={
                        <>
                            Showing {showingFrom}-{showingTo} of {totalCount} results
                        </>
                    }
                />
            )}
        </section>
    );
};
