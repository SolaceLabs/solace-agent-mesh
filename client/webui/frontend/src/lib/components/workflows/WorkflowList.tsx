import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig } from "@/lib/utils/agentUtils";
import { SearchInput } from "@/lib/components/ui";
import { EmptyState } from "@/lib/components/common";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui/table";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/lib/components/ui/pagination";
import { Workflow } from "lucide-react";
import { WorkflowDetailPanel } from "./WorkflowDetailPanel";
import { WorkflowOnboardingBanner } from "./WorkflowOnboardingBanner";

// Panel width configuration (pixels)
const DETAIL_PANEL_WIDTHS = { default: 400, min: 280, max: 800 };

const WorkflowImage = <Workflow className="text-muted-foreground" size={64} />;

const ITEMS_PER_PAGE = 20;

interface WorkflowListProps {
    workflows: AgentCardInfo[];
}

export const WorkflowList: React.FC<WorkflowListProps> = ({ workflows }) => {
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [selectedWorkflow, setSelectedWorkflow] = useState<AgentCardInfo | null>(null);
    const [panelWidth, setPanelWidth] = useState<number>(DETAIL_PANEL_WIDTHS.default);
    const [shouldAnimate, setShouldAnimate] = useState(false);
    const prevSelectedRef = useRef<AgentCardInfo | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const isResizing = useRef(false);

    // Track when panel opens to trigger animation only on initial open
    useEffect(() => {
        if (selectedWorkflow && !prevSelectedRef.current) {
            // Panel just opened
            setShouldAnimate(true);
            const timer = setTimeout(() => setShouldAnimate(false), 300);
            return () => clearTimeout(timer);
        }
        prevSelectedRef.current = selectedWorkflow;
    }, [selectedWorkflow]);

    // Handle resize drag
    const handleResizeStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        isResizing.current = true;
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        const handleMouseMove = (e: MouseEvent) => {
            if (!isResizing.current || !containerRef.current) return;
            const containerRect = containerRef.current.getBoundingClientRect();
            const newWidth = containerRect.right - e.clientX;
            setPanelWidth(Math.max(DETAIL_PANEL_WIDTHS.min, Math.min(DETAIL_PANEL_WIDTHS.max, newWidth)));
        };

        const handleMouseUp = () => {
            isResizing.current = false;
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
        };

        document.addEventListener("mousemove", handleMouseMove);
        document.addEventListener("mouseup", handleMouseUp);
    }, []);

    const filteredWorkflows = useMemo(() => {
        return workflows.filter(workflow => (workflow.displayName || workflow.name)?.toLowerCase().includes(searchQuery.toLowerCase()));
    }, [workflows, searchQuery]);

    const totalPages = Math.ceil(filteredWorkflows.length / ITEMS_PER_PAGE);
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    const paginatedWorkflows = filteredWorkflows.slice(startIndex, endIndex);

    const handleRowClick = (workflow: AgentCardInfo) => {
        setSelectedWorkflow(workflow);
    };

    const handleClosePanel = () => {
        setSelectedWorkflow(null);
    };

    const handlePageChange = (page: number) => {
        if (page >= 1 && page <= totalPages) {
            setCurrentPage(page);
        }
    };

    const getWorkflowDescription = (workflow: AgentCardInfo): string => {
        const config = getWorkflowConfig(workflow);
        return config?.description || workflow.description || "No description";
    };

    const renderPaginationNumbers = () => {
        const pages: (number | "ellipsis")[] = [];
        const maxVisiblePages = 5;

        if (totalPages <= maxVisiblePages) {
            for (let i = 1; i <= totalPages; i++) {
                pages.push(i);
            }
        } else {
            pages.push(1);
            if (currentPage > 3) {
                pages.push("ellipsis");
            }
            const start = Math.max(2, currentPage - 1);
            const end = Math.min(totalPages - 1, currentPage + 1);
            for (let i = start; i <= end; i++) {
                pages.push(i);
            }
            if (currentPage < totalPages - 2) {
                pages.push("ellipsis");
            }
            pages.push(totalPages);
        }

        return pages.map((page, index) =>
            page === "ellipsis" ? (
                <PaginationItem key={`ellipsis-${index}`}>
                    <PaginationEllipsis />
                </PaginationItem>
            ) : (
                <PaginationItem key={page}>
                    <PaginationLink onClick={() => handlePageChange(page)} isActive={currentPage === page} className="cursor-pointer">
                        {page}
                    </PaginationLink>
                </PaginationItem>
            )
        );
    };

    if (workflows.length === 0) {
        return <EmptyState image={WorkflowImage} title="No workflows found" subtitle="No workflows discovered in the current namespace." />;
    }

    return (
        <div ref={containerRef} className="bg-muted relative flex h-full flex-col dark:bg-[var(--color-bg-wMain)]">
            <WorkflowOnboardingBanner />
            <div className="flex min-h-0 flex-1 flex-col px-6 pt-6">
                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testid="workflowSearchInput" className="mb-4 w-xs" />

                {filteredWorkflows.length === 0 && searchQuery ? (
                    <EmptyState variant="notFound" title="No Workflows Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => setSearchQuery("") }]} />
                ) : (
                    <div className="flex min-h-0 flex-1 flex-col pb-6">
                        <div className="bg-background flex min-h-0 flex-1 flex-col overflow-auto rounded-sm border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[250px]">Name</TableHead>
                                        <TableHead className="w-[100px]">Version</TableHead>
                                        <TableHead className="w-[100px]">Status</TableHead>
                                        <TableHead>Description</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {paginatedWorkflows.map(workflow => (
                                        <TableRow
                                            key={workflow.name}
                                            onClick={() => handleRowClick(workflow)}
                                            className={`cursor-pointer ${selectedWorkflow?.name === workflow.name ? "bg-gray-100 dark:bg-gray-700" : ""}`}
                                        >
                                            <TableCell className="font-medium">{workflow.displayName || workflow.name}</TableCell>
                                            <TableCell className="text-muted-foreground">{workflow.version || "N/A"}</TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <div className="h-2 w-2 rounded-full bg-[var(--color-success-wMain)]"></div>
                                                    <span>Online</span>
                                                </div>
                                            </TableCell>
                                            <TableCell className="max-w-md truncate">{getWorkflowDescription(workflow)}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>

                        {totalPages > 1 && (
                            <div className="bg-background mt-4 flex flex-shrink-0 justify-center border-t pt-4 pb-2">
                                <Pagination>
                                    <PaginationContent>
                                        <PaginationItem>
                                            <PaginationPrevious onClick={() => handlePageChange(currentPage - 1)} className={currentPage === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"} />
                                        </PaginationItem>
                                        {renderPaginationNumbers()}
                                        <PaginationItem>
                                            <PaginationNext onClick={() => handlePageChange(currentPage + 1)} className={currentPage === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"} />
                                        </PaginationItem>
                                    </PaginationContent>
                                </Pagination>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Detail panel overlay (shown when workflow selected) */}
            {selectedWorkflow && (
                <div
                    className={`absolute top-0 right-0 bottom-0 z-10 flex ${shouldAnimate ? "animate-in slide-in-from-right duration-300" : ""}`}
                    style={{ width: panelWidth }}
                >
                    {/* Resize handle - matches ResizableHandle styling */}
                    <div
                        className="bg-border relative flex w-px cursor-col-resize items-center justify-center after:absolute after:inset-y-0 after:left-1/2 after:w-1 after:-translate-x-1/2"
                        onMouseDown={handleResizeStart}
                    />
                    {/* Panel content */}
                    <div className="bg-background min-w-0 flex-1">
                        <WorkflowDetailPanel workflow={selectedWorkflow} onClose={handleClosePanel} />
                    </div>
                </div>
            )}
        </div>
    );
};
