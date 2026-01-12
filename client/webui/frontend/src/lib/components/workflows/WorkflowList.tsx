import React, { useState, useMemo } from "react";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig } from "@/lib/utils/agentUtils";
import { SearchInput } from "@/lib/components/ui";
import { EmptyState } from "@/lib/components/common";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui/table";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/lib/components/ui/pagination";
import { Workflow } from "lucide-react";
import { WorkflowDetailPanel } from "./WorkflowDetailPanel";
import { WorkflowOnboardingBanner } from "./WorkflowOnboardingBanner";

const WorkflowImage = <Workflow className="text-muted-foreground" size={64} />;

const ITEMS_PER_PAGE = 20;

interface WorkflowListProps {
    workflows: AgentCardInfo[];
}

export const WorkflowList: React.FC<WorkflowListProps> = ({ workflows }) => {
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [selectedWorkflow, setSelectedWorkflow] = useState<AgentCardInfo | null>(null);

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
                    <span className="px-2">...</span>
                </PaginationItem>
            ) : (
                <PaginationItem key={page}>
                    <PaginationLink href="#" isActive={currentPage === page} onClick={e => { e.preventDefault(); handlePageChange(page); }}>
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
        <>
            <div className="flex h-full flex-col">
                <WorkflowOnboardingBanner />
                <div className="bg-card-background flex-1 px-6 pt-6">
                    <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testid="workflowSearchInput" className="mb-4 w-xs" />

                    {filteredWorkflows.length === 0 && searchQuery ? (
                        <EmptyState variant="notFound" title="No Workflows Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => setSearchQuery("") }]} />
                    ) : (
                        <div className="flex flex-col">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[250px]">Name</TableHead>
                                        <TableHead className="w-[100px]">Status</TableHead>
                                        <TableHead>Description</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {paginatedWorkflows.map(workflow => (
                                        <TableRow key={workflow.name} onClick={() => handleRowClick(workflow)} className="cursor-pointer">
                                            <TableCell className="font-medium">{workflow.displayName || workflow.name}</TableCell>
                                            <TableCell>
                                                <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900 dark:text-green-200">Online</span>
                                            </TableCell>
                                            <TableCell className="max-w-md truncate">{getWorkflowDescription(workflow)}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>

                            {totalPages > 1 && (
                                <div className="mt-4 flex items-center justify-between border-t pt-4">
                                    <div className="text-muted-foreground text-sm">
                                        Showing {startIndex + 1}-{Math.min(endIndex, filteredWorkflows.length)} of {filteredWorkflows.length} results
                                    </div>
                                    <Pagination>
                                        <PaginationContent>
                                            <PaginationItem>
                                                <PaginationPrevious href="#" onClick={e => { e.preventDefault(); handlePageChange(currentPage - 1); }} className={currentPage === 1 ? "pointer-events-none opacity-50" : ""} />
                                            </PaginationItem>
                                            {renderPaginationNumbers()}
                                            <PaginationItem>
                                                <PaginationNext href="#" onClick={e => { e.preventDefault(); handlePageChange(currentPage + 1); }} className={currentPage === totalPages ? "pointer-events-none opacity-50" : ""} />
                                            </PaginationItem>
                                        </PaginationContent>
                                    </Pagination>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <WorkflowDetailPanel workflow={selectedWorkflow} onClose={handleClosePanel} />
        </>
    );
};
