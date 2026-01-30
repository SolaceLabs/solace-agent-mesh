import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import type { AgentCardInfo } from "@/lib/types";
import { EmptyState, OnboardingBanner, OnboardingView } from "@/lib/components/common";
import { Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/lib/components/ui/pagination";
import { WorkflowDetailPanel } from "./WorkflowDetailPanel";
import { SearchInput } from "..";
import { Workflow } from "lucide-react";

const WORKFLOW_STORAGE_KEY = "sam-workflow-onboarding-dismissed";
const WORKFLOW_URL = "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/components/workflows";
const WORKFLOW_HEADER = "Workflows give enterprises production-ready, best-practice agent patterns that are predictable and reliable.";
const WORKFLOW_DESCRIPTION =
    "Turn complex multi-agent tasks into streamlined workflows. Define the sequence in YAML, deploy to Agent Mesh, and watch your workflow handle the coordination automatically. Great for building repeatable processes that need multiple agents working together in a specific order.";
const WORKFLOW_LEARN_MORE_TEXT = "Learn how to create workflows";

interface WorkflowListProps {
    workflows: AgentCardInfo[];
    className?: string;
}

export const WorkflowList = ({ workflows, className }: WorkflowListProps) => {
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

        const result = searchTerm.trim() ? workflows.filter(workflow => (workflow.displayName || workflow.name)?.toLowerCase().includes(searchTerm.toLowerCase())) : workflows;

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
                setIsSidePanelOpen(true);
            }
        }
    };

    const handleCloseSidePanel = () => {
        setIsSidePanelOpen(false);
        setSelectedWorkflow(null);
    };

    const handleViewWorkflow = (workflow: AgentCardInfo) => {
        navigate(`/agents/workflows/${encodeURIComponent(workflow.name)}`);
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
        return <OnboardingView title={WORKFLOW_HEADER} description={WORKFLOW_DESCRIPTION} learnMoreText={WORKFLOW_LEARN_MORE_TEXT} learnMoreHref={WORKFLOW_URL} image={<Workflow className={"text-(--color-brand-wMain)"} size={128} />} />;
    }

    // Pagination controls component
    const PaginationControls = () => {
        if (totalPages <= 1) return null;

        return (
            <div className="border-border bg-background mt-4 flex flex-shrink-0 justify-center border-t pt-4 pb-2">
                <Pagination>
                    <PaginationContent>
                        <PaginationItem>
                            <PaginationPrevious onClick={() => handlePageChange(effectiveCurrentPage - 1)} className={effectiveCurrentPage === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"} />
                        </PaginationItem>

                        {getPageNumbers().map((page, index) => (
                            <PaginationItem key={index}>
                                {page === "ellipsis" ? (
                                    <PaginationEllipsis />
                                ) : (
                                    <PaginationLink onClick={() => handlePageChange(page as number)} isActive={effectiveCurrentPage === page} className="cursor-pointer">
                                        {page}
                                    </PaginationLink>
                                )}
                            </PaginationItem>
                        ))}

                        <PaginationItem>
                            <PaginationNext onClick={() => handlePageChange(effectiveCurrentPage + 1)} className={effectiveCurrentPage === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"} />
                        </PaginationItem>
                    </PaginationContent>
                </Pagination>
            </div>
        );
    };

    return (
        <div className={`flex h-full w-full ${className ?? ""}`}>
            {/* Main content container */}
            <div className="flex flex-1 flex-col py-6 pl-6">
                <OnboardingBanner storageKey={WORKFLOW_STORAGE_KEY} header={WORKFLOW_HEADER} description={WORKFLOW_DESCRIPTION} learnMoreText={WORKFLOW_LEARN_MORE_TEXT} learnMoreUrl={WORKFLOW_URL} className="mr-6 mb-6" />
                <SearchInput value={searchTerm} onChange={value => setSearchTerm(value)} />

                <div className="min-h-0 flex-1 overflow-y-auto pt-6 pr-6">
                    <div className="h-full">
                        {currentWorkflows.length > 0 ? (
                            <div className="rounded-xs border">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="font-semibold">
                                                <div className="pl-4">Name</div>
                                            </TableHead>
                                            <TableHead className="w-1/4 font-semibold">Version</TableHead>
                                            <TableHead className="w-1/4 font-semibold">Status</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {currentWorkflows.map(workflow => (
                                            <TableRow key={workflow.name} onClick={() => handleSelectWorkflow(workflow)} className="hover:bg-muted/50 cursor-pointer" data-state={selectedWorkflow?.name === workflow.name ? "selected" : undefined}>
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
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        ) : (
                            <div className="flex h-full min-h-[300px] items-center justify-center">
                                <EmptyState variant="notFound" title="No workflows found" subtitle="Try adjusting your search terms" buttons={[{ text: "Clear Filter", variant: "default", onClick: () => setSearchTerm("") }]} />
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
