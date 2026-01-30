import React, { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Workflow } from "lucide-react";

import { Button, EmptyState } from "@/lib/components";
import { Header, type BreadcrumbItem } from "@/lib/components/header";
import { useChatContext } from "@/lib/hooks";
import { isWorkflowAgent, getWorkflowConfig } from "@/lib/utils/agentUtils";
import type { LayoutNode } from "./utils/types";
import { extractNodeIdsFromConfig } from "./utils/expressionParser";
import { processWorkflowConfig } from "./utils/layoutEngine";
import WorkflowDiagram from "./WorkflowDiagram";
import WorkflowNodeDetailPanel from "./WorkflowNodeDetailPanel";
import WorkflowDetailsSidePanel, { type WorkflowPanelView } from "./WorkflowDetailsSidePanel";
import CanvasControls from "./CanvasControls";
import type { PanZoomCanvasRef } from "@/lib/components/activities/FlowChart/PanZoomCanvas";

// Panel width configuration (pixels)
const DETAIL_PANEL_WIDTHS = { default: 400, min: 280, max: 800 };

/**
 * WorkflowVisualizationPage - Main page for viewing workflow node diagrams
 * Accessible via /agents/workflows/:workflowName
 */
/**
 * Builds a navigation URL to a workflow with parent path tracking.
 * @param targetWorkflow The workflow to navigate to
 * @param parentPath The parent workflows leading to this navigation (closest parent first)
 */
export function buildWorkflowNavigationUrl(targetWorkflow: string, parentPath: string[] = []): string {
    const encodedTarget = encodeURIComponent(targetWorkflow);
    if (parentPath.length === 0) {
        return `/agents/workflows/${encodedTarget}`;
    }
    const fromParam = parentPath.map(encodeURIComponent).join(",");
    return `/agents/workflows/${encodedTarget}?from=${fromParam}`;
}

export function WorkflowVisualizationPage() {
    const { workflowName } = useParams<{ workflowName: string }>();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { agents, agentsLoading, agentsError } = useChatContext();

    // Parse parent workflow path from URL search params
    // Format: ?from=parent1,parent2,... (closest parent first)
    const parentPath = useMemo(() => {
        const fromParam = searchParams.get("from");
        if (!fromParam) return [];
        return fromParam.split(",").map(decodeURIComponent);
    }, [searchParams]);

    const [selectedNode, setSelectedNode] = useState<LayoutNode | null>(null);
    const [workflowPanelView, setWorkflowPanelView] = useState<WorkflowPanelView | null>(null);
    const [panelWidth, setPanelWidth] = useState<number>(DETAIL_PANEL_WIDTHS.default);
    const [shouldAnimate, setShouldAnimate] = useState(false);
    const [highlightedNodeIds, setHighlightedNodeIds] = useState<Set<string>>(new Set());
    const [currentZoom, setCurrentZoom] = useState(1);
    const prevSelectedRef = useRef<LayoutNode | null>(null);
    const prevWorkflowPanelRef = useRef<WorkflowPanelView | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<PanZoomCanvasRef>(null);
    const contentWidthRef = useRef(800);
    const isResizing = useRef(false);

    // Track when panel opens to trigger animation only on initial open
    useEffect(() => {
        const nodeJustOpened = selectedNode && !prevSelectedRef.current;
        const workflowPanelJustOpened = workflowPanelView && !prevWorkflowPanelRef.current;

        // Update refs immediately so switching views doesn't re-trigger animation
        prevSelectedRef.current = selectedNode;
        prevWorkflowPanelRef.current = workflowPanelView;

        if (nodeJustOpened || workflowPanelJustOpened) {
            setShouldAnimate(true);
            const timer = setTimeout(() => setShouldAnimate(false), 300);
            return () => clearTimeout(timer);
        }
    }, [selectedNode, workflowPanelView]);

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

    // Find the workflow and extract config
    const { workflow, config, knownWorkflows } = useMemo(() => {
        const workflowAgents = agents.filter(isWorkflowAgent);
        const foundWorkflow = workflowAgents.find(agent => agent.name === workflowName || agent.displayName === workflowName);
        const workflowConfig = foundWorkflow ? getWorkflowConfig(foundWorkflow) : null;

        // Build set of known workflow names for detecting nested workflow references
        const knownWorkflowNames = new Set(workflowAgents.map(w => w.name));

        return {
            workflow: foundWorkflow,
            config: workflowConfig,
            knownWorkflows: knownWorkflowNames,
        };
    }, [agents, workflowName]);

    // Compute known node IDs from config for expression parsing
    const knownNodeIds = useMemo(() => {
        if (!config) return new Set<string>();
        return extractNodeIdsFromConfig(config);
    }, [config]);

    // Handle highlighting nodes when hovering over expressions
    const handleHighlightNodes = useCallback((nodeIds: string[]) => {
        setHighlightedNodeIds(new Set(nodeIds));
    }, []);

    // Handle node selection
    const handleNodeSelect = useCallback((node: LayoutNode | null) => {
        setWorkflowPanelView(null); // Close workflow panel if open
        setSelectedNode(node);
    }, []);

    // Handle opening workflow details panel
    const handleOpenWorkflowDetails = useCallback(() => {
        setSelectedNode(null); // Close node panel if open
        setWorkflowPanelView("details");
    }, []);

    // Handle closing workflow panel
    const handleCloseWorkflowPanel = useCallback(() => {
        setWorkflowPanelView(null);
    }, []);

    // Handle switching panel view (details <-> code)
    const handleSwitchPanelView = useCallback((view: WorkflowPanelView) => {
        setWorkflowPanelView(view);
    }, []);

    // Handle transform changes from canvas (for zoom level display)
    const handleTransformChange = useCallback((transform: { scale: number; x: number; y: number }) => {
        setCurrentZoom(transform.scale);
    }, []);

    // Zoom control handlers
    const handleZoomIn = useCallback(() => {
        canvasRef.current?.zoomIn({ animated: true });
    }, []);

    const handleZoomOut = useCallback(() => {
        canvasRef.current?.zoomOut({ animated: true });
    }, []);

    const handleFitToView = useCallback(() => {
        canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
    }, []);

    // Track content size for fit-to-view
    const handleContentSizeChange = useCallback((width: number) => {
        contentWidthRef.current = width;
    }, []);

    // Handle navigation to a node (pan to center it in view)
    const handleNavigateToNode = useCallback(
        (nodeId: string) => {
            if (!config) return;

            // Compute layout to find node position
            const layout = processWorkflowConfig(config, new Set(), knownWorkflows);

            // Find the node in the layout (search recursively)
            const findNode = (nodes: LayoutNode[]): LayoutNode | null => {
                for (const node of nodes) {
                    if (node.id === nodeId) return node;
                    if (node.children) {
                        const found = findNode(node.children);
                        if (found) return found;
                    }
                }
                return null;
            };

            const targetNode = findNode(layout.nodes);
            if (targetNode) {
                // Pan to center the node (use center of the node)
                const centerX = targetNode.x + targetNode.width / 2;
                const centerY = targetNode.y + targetNode.height / 2;
                canvasRef.current?.panToPoint(centerX, centerY, { animated: true });
            }
        },
        [config, knownWorkflows]
    );

    // Build breadcrumbs for navigation
    // Include parent workflows from the navigation path
    const breadcrumbs: BreadcrumbItem[] = useMemo(() => {
        const items: BreadcrumbItem[] = [
            { label: "Agents", onClick: () => navigate("/agents") },
            { label: "Workflows", onClick: () => navigate("/agents?tab=workflows") },
        ];

        // Add parent workflow breadcrumbs
        parentPath.forEach((parentName, index) => {
            // Find the parent workflow to get display name
            const workflowAgents = agents.filter(isWorkflowAgent);
            const parentWorkflow = workflowAgents.find(agent => agent.name === parentName || agent.displayName === parentName);
            const displayLabel = parentWorkflow?.displayName || parentWorkflow?.name || parentName;

            // When clicking a parent, navigate to it with its own parent path
            // (all parents after this one in the array)
            const parentOfParent = parentPath.slice(index + 1);
            items.push({
                label: displayLabel,
                onClick: () => navigate(buildWorkflowNavigationUrl(parentName, parentOfParent)),
            });
        });

        // Add current workflow (not clickable)
        items.push({
            label: workflow?.displayName || workflow?.name || workflowName || "Workflow",
        });

        return items;
    }, [navigate, parentPath, workflow, workflowName, agents]);

    // Loading state
    if (agentsLoading) {
        return (
            <div className="flex h-full w-full flex-col">
                <Header
                    title={
                        <div className="flex items-center gap-2">
                            <Workflow className="h-5 w-5 text-(--color-brand-wMain)" />
                            <span>{workflowName || "Workflow"}</span>
                        </div>
                    }
                    breadcrumbs={breadcrumbs}
                />
                <EmptyState title="Loading..." variant="loading" />
            </div>
        );
    }

    // Error state
    if (agentsError) {
        return (
            <div className="flex h-full w-full flex-col">
                <Header
                    title={
                        <div className="flex items-center gap-2">
                            <Workflow className="h-5 w-5 text-(--color-brand-wMain)" />
                            <span>{workflowName || "Workflow"}</span>
                        </div>
                    }
                    breadcrumbs={breadcrumbs}
                />
                <EmptyState variant="error" title="Error loading data" subtitle={agentsError} />
            </div>
        );
    }

    // Workflow not found
    if (!workflow || !config) {
        return (
            <div className="flex h-full w-full flex-col">
                <Header
                    title={
                        <div className="flex items-center gap-2">
                            <Workflow className="h-5 w-5 text-(--color-brand-wMain)" />
                            <span>{workflowName || "Workflow"}</span>
                        </div>
                    }
                    breadcrumbs={breadcrumbs}
                />
                <EmptyState variant="error" title="Workflow not found" subtitle={`Could not find a workflow named "${workflowName}"`} />
            </div>
        );
    }

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title={
                    <div className="flex items-center gap-2">
                        <Workflow className="h-5 w-5 text-(--color-brand-wMain)" />
                        <span>{workflow.displayName || workflow.name}</span>
                        {config.version && <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-400">v{config.version}</span>}
                    </div>
                }
                breadcrumbs={breadcrumbs}
                buttons={[
                    <Button variant="ghost" key="details" onClick={handleOpenWorkflowDetails}>
                        Open Workflow Details
                    </Button>,
                ]}
            />

            {/* Canvas controls bar */}
            <CanvasControls zoomLevel={currentZoom} onZoomIn={handleZoomIn} onZoomOut={handleZoomOut} onFitToView={handleFitToView} minZoom={0.25} maxZoom={2} />

            {/* Body container - panels overlay this area only */}
            <div ref={containerRef} className="relative min-h-0 flex-1">
                <WorkflowDiagram
                    config={config}
                    knownWorkflows={knownWorkflows}
                    onNodeSelect={handleNodeSelect}
                    highlightedNodeIds={highlightedNodeIds}
                    onHighlightNodes={handleHighlightNodes}
                    knownNodeIds={knownNodeIds}
                    onTransformChange={handleTransformChange}
                    canvasRef={canvasRef}
                    onContentSizeChange={handleContentSizeChange}
                    currentWorkflowName={workflow.name}
                    parentPath={parentPath}
                />

                {/* Floating node detail popover (shown when node selected) */}
                {selectedNode && (
                    <div className={`absolute top-4 right-4 bottom-4 z-10 overflow-hidden rounded-lg border shadow-lg ${shouldAnimate ? "animate-in slide-in-from-right duration-300" : ""}`} style={{ width: panelWidth }}>
                        <WorkflowNodeDetailPanel
                            node={selectedNode}
                            workflowConfig={config}
                            agents={agents}
                            onHighlightNodes={handleHighlightNodes}
                            knownNodeIds={knownNodeIds}
                            onNavigateToNode={handleNavigateToNode}
                            currentWorkflowName={workflow.name}
                            parentPath={parentPath}
                        />
                    </div>
                )}

                {/* Workflow Details / Raw Code Side Panel */}
                {workflowPanelView && (
                    <div className={`absolute top-0 right-0 bottom-0 z-10 flex ${shouldAnimate ? "animate-in slide-in-from-right duration-300" : ""}`} style={{ width: panelWidth }}>
                        {/* Resize handle - matches ResizableHandle styling */}
                        <div className="bg-border relative flex w-px cursor-col-resize items-center justify-center after:absolute after:inset-y-0 after:left-1/2 after:w-1 after:-translate-x-1/2" onMouseDown={handleResizeStart} />
                        {/* Panel content */}
                        <div className="bg-background min-w-0 flex-1">
                            <WorkflowDetailsSidePanel workflow={workflow} config={config} view={workflowPanelView} onClose={handleCloseWorkflowPanel} onViewChange={handleSwitchPanelView} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default WorkflowVisualizationPage;
