import React, { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Workflow } from "lucide-react";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig } from "@/lib/utils/agentUtils";
import { EmptyState } from "@/lib/components/common";
import { Button } from "@/lib/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui/table";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/lib/components/ui/pagination";
import { WorkflowDetailPanel } from "./WorkflowDetailPanel";
import { WorkflowOnboardingBanner } from "./WorkflowOnboardingBanner";

const WorkflowImage = <Workflow className="text-muted-foreground" size={64} />;

interface WorkflowListProps {
    workflows: AgentCardInfo[];
}

export const WorkflowList: React.FC<WorkflowListProps> = ({ workflows }) => {
    const navigate = useNavigate();
    const [searchTerm, setSearchTerm] = useState<string>("");
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [screenHeight, setScreenHeight] = useState<number>(typeof window !== "undefined" ? window.innerHeight : 768);
    const [selectedWorkflow, setSelectedWorkflow] = useState<AgentCardInfo | null>(null);
    const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(false);

    // Responsive itemsPerPage based on screen height
    const itemsPerPage = screenHeight >= 900 ? 20 : 10;

    // Handle screen resize
    useEffect(() => {
        const handleResize = () => {
            if (typeof window !== "undefined") {
                setScreenHeight(window.innerHeight);
            }
        };

        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    // Filter and sort workflows
    const filteredWorkflows = useMemo(() => {
        if (!workflows || workflows.length === 0) return [];

        let result = searchTerm.trim()
            ? workflows.filter(workflow => (workflow.displayName || workflow.name)?.toLowerCase().includes(searchTerm.toLowerCase()))
            : workflows;

        return result.slice().sort((a, b) => (a.displayName || a.name).localeCompare(b.displayName || b.name));
    }, [workflows, searchTerm]);

    // Calculate pagination
    const totalPages = Math.ceil(filteredWorkflows.length / itemsPerPage);
    const effectiveCurrentPage = Math.min(currentPage, Math.max(totalPages, 1));
    const startIndex = (effectiveCurrentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentWorkflows = filteredWorkflows.slice(startIndex, endIndex);

    // Reset to page 1 when search changes
    useEffect(() => {
        setCurrentPage(1);
    }, [searchTerm]);

    // Close side panel when workflows list changes (e.g., workflow removed)
    useEffect(() => {
        if (!selectedWorkflow) return;
        if (workflows?.some(workflow => workflow.name === selectedWorkflow.name) === false) {
            setIsSidePanelOpen(false);
            setSelectedWorkflow(null);
        }
    }, [workflows, selectedWorkflow]);

    const handlePageChange = (page: number) => {
        if (page >= 1 && page <= totalPages) {
            setCurrentPage(page);
        }
    };

    const handleSelectWorkflow = (workflow: AgentCardInfo | null) => {
        if (workflow) {
            // If clicking the same workflow, close the panel
            if (selectedWorkflow?.name === workflow.name && isSidePanelOpen) {
                handleCloseSidePanel();
            } else {
                // Open panel for new workflow
                setSelectedWorkflow(workflow);
                setTimeout(() => setIsSidePanelOpen(true), 10);
            }
        }
    };

    const handleCloseSidePanel = () => {
        setIsSidePanelOpen(false);
        setTimeout(() => setSelectedWorkflow(null), 300);
    };

    const handleViewWorkflow = (workflow: AgentCardInfo) => {
        navigate(`/agents/workflows/${encodeURIComponent(workflow.name)}`);
    };

    const getWorkflowDescription = (workflow: AgentCardInfo): string => {
        const config = getWorkflowConfig(workflow);
        return config?.description || workflow.description || "No description";
    };

    const getPageNumbers = () => {
        const pages: (number | string)[] = [];
        const maxVisiblePages = 5;

        if (totalPages <= maxVisiblePages) {
            for (let i = 1; i <= totalPages; i++) {
                pages.push(i);
            }
        } else {
            if (effectiveCurrentPage <= 3) {
                for (let i = 1; i <= 4; i++) {
                    pages.push(i);
                }
                pages.push("ellipsis");
                pages.push(totalPages);
            } else if (effectiveCurrentPage >= totalPages - 2) {
                pages.push(1);
                pages.push("ellipsis");
                for (let i = totalPages - 3; i <= totalPages; i++) {
                    pages.push(i);
                }
            } else {
                pages.push(1);
                pages.push("ellipsis");
                for (let i = effectiveCurrentPage - 1; i <= effectiveCurrentPage + 1; i++) {
                    pages.push(i);
                }
                pages.push("ellipsis");
                pages.push(totalPages);
            }
        }

        return pages;
    };

    if (workflows.length === 0) {
        return <EmptyState image={WorkflowImage} title="No workflows found" subtitle="No workflows discovered in the current namespace." />;
    }

    // Pagination controls component
    const PaginationControls = () => {
        if (totalPages <= 1) return null;

        return (
            <div className="border-border bg-background mt-4 flex flex-shrink-0 justify-center border-t pt-4 pb-2">
                <Pagination>
                    <PaginationContent>
                        <PaginationItem>
                            <PaginationPrevious
                                onClick={() => handlePageChange(effectiveCurrentPage - 1)}
                                className={effectiveCurrentPage === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                            />
                        </PaginationItem>

                        {getPageNumbers().map((page, index) => (
                            <PaginationItem key={index}>
                                {page === "ellipsis" ? (
                                    <PaginationEllipsis />
                                ) : (
                                    <PaginationLink
                                        onClick={() => handlePageChange(page as number)}
                                        isActive={effectiveCurrentPage === page}
                                        className="cursor-pointer"
                                    >
                                        {page}
                                    </PaginationLink>
                                )}
                            </PaginationItem>
                        ))}

                        <PaginationItem>
                            <PaginationNext
                                onClick={() => handlePageChange(effectiveCurrentPage + 1)}
                                className={effectiveCurrentPage === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                            />
                        </PaginationItem>
                    </PaginationContent>
                </Pagination>
            </div>
        );
    };

    return (
        <div className="flex h-full w-full overflow-hidden">
            {/* Main content container */}
            <div className="flex flex-1 flex-col">
                <WorkflowOnboardingBanner />
                {/* Search Bar */}
                <div className="mb-4 flex items-center justify-between p-6">
                    <div className="flex w-full max-w-md flex-shrink-0 items-center gap-4">
                        <div className="relative flex-1">
                            <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                            <input
                                type="text"
                                placeholder="Filter by name..."
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                                data-testid="workflowSearchInput"
                                className="border-input bg-background placeholder:text-muted-foreground focus:border-ring w-full rounded-sm border px-10 py-2 text-sm focus:outline-none"
                            />
                        </div>
                    </div>
                </div>

                {/* Workflows table area */}
                <div className="min-h-0 flex-1 overflow-y-auto pr-6 pl-6">
                    <div className="h-full">
                        {currentWorkflows.length > 0 ? (
                            <div className="rounded-xs border">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="font-semibold">
                                                <div className="pl-4">Name</div>
                                            </TableHead>
                                            <TableHead className="w-[100px] font-semibold">Version</TableHead>
                                            <TableHead className="w-[100px] font-semibold">Status</TableHead>
                                            <TableHead className="font-semibold">Description</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {currentWorkflows.map(workflow => (
                                            <TableRow
                                                key={workflow.name}
                                                onClick={() => handleSelectWorkflow(workflow)}
                                                className="hover:bg-muted/50 cursor-pointer"
                                                data-state={selectedWorkflow?.name === workflow.name ? "selected" : undefined}
                                            >
                                                <TableCell>
                                                    <Button
                                                        testid={`workflow-name-${workflow.name}`}
                                                        title={workflow.displayName || workflow.name}
                                                        variant="link"
                                                        onClick={e => {
                                                            e.stopPropagation();
                                                            handleViewWorkflow(workflow);
                                                        }}
                                                    >
                                                        {workflow.displayName || workflow.name}
                                                    </Button>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">{workflow.version || "N/A"}</TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <div className="h-2 w-2 rounded-full bg-[var(--color-success-wMain)]"></div>
                                                        <span>Running</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="max-w-md truncate">{getWorkflowDescription(workflow)}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        ) : (
                            <div className="flex h-full min-h-[300px] items-center justify-center">
                                <EmptyState
                                    variant="notFound"
                                    title="No workflows found"
                                    subtitle="Try adjusting your search terms"
                                    buttons={[{ text: "Clear Filter", variant: "default", onClick: () => setSearchTerm("") }]}
                                />
                            </div>
                        )}
                    </div>
                </div>
                <PaginationControls />
            </div>

            {/* Side panel wrapper */}
            {selectedWorkflow && (
                <div className={`h-full overflow-hidden transition-[width] duration-300 ease-in-out ${isSidePanelOpen ? "w-[400px]" : "w-0"}`}>
                    <div className={`h-full transition-opacity duration-300 ${isSidePanelOpen ? "opacity-100 delay-100" : "pointer-events-none opacity-0"}`}>
                        <WorkflowDetailPanel workflow={selectedWorkflow} onClose={handleCloseSidePanel} />
                    </div>
                </div>
            )}
        </div>
    );
};
