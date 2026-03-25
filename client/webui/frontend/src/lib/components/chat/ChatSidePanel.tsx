import React, { useState, useEffect, useMemo } from "react";

import { PanelRightIcon, FileText, Network, RefreshCw, Link2 } from "lucide-react";

import { Button, Tabs, TabsList, TabsTrigger, TabsContent } from "@/lib/components/ui";
import { useTaskContext, useChatContext, useIsProjectIndexingEnabled } from "@/lib/hooks";
import { FlowChartPanel, processTaskForVisualization } from "@/lib/components/activities";
import type { VisualizedTask } from "@/lib/types";
import { hasSourcesWithUrls, hasDocumentSearchResults } from "@/lib/utils";

import { ArtifactPanel } from "./artifact/ArtifactPanel";
import { FlowChartDetails } from "../activities/FlowChartDetails";
import { RAGInfoPanel } from "./rag/RAGInfoPanel";
import { DocumentSourcesPanel } from "./rag/DocumentSourcesPanel";

interface ChatSidePanelProps {
    onCollapsedToggle: (isSidePanelCollapsed: boolean) => void;
    isSidePanelCollapsed: boolean;
    setIsSidePanelCollapsed: (isSidePanelCollapsed: boolean) => void;
    isSidePanelTransitioning: boolean;
}

export const ChatSidePanel: React.FC<ChatSidePanelProps> = ({ onCollapsedToggle, isSidePanelCollapsed, setIsSidePanelCollapsed, isSidePanelTransitioning }) => {
    const { activeSidePanelTab, setActiveSidePanelTab, setPreviewArtifact, taskIdInSidePanel, ragData, ragEnabled } = useChatContext();
    const { isReconnecting, isTaskMonitorConnecting, isTaskMonitorConnected, monitoredTasks, connectTaskMonitorStream, loadTaskFromBackend } = useTaskContext();
    const isProjectIndexingEnabled = useIsProjectIndexingEnabled();
    const [visualizedTask, setVisualizedTask] = useState<VisualizedTask | null>(null);
    const [isLoadingTask, setIsLoadingTask] = useState<boolean>(false);

    // Track which task IDs we've already attempted to load to prevent duplicate loads
    const loadAttemptedRef = React.useRef<Set<string>>(new Set());

    const filteredRagData = taskIdInSidePanel ? ragData.filter(r => r.taskId === taskIdInSidePanel) : ragData;

    // Check if there are any sources in the current session
    // Includes: web sources, deep research sources, AND document search sources
    const hasSourcesInSession = useMemo(() => {
        if (!ragData || ragData.length === 0) return false;

        // Check for web/research sources with URLs (existing behavior)
        if (hasSourcesWithUrls(ragData)) return true;

        // Also check for document search results
        return hasDocumentSearchResults(ragData);
    }, [ragData]);

    // Process task data for visualization when the selected activity task ID changes
    // or when monitoredTasks is updated with new data.
    useEffect(() => {
        if (!taskIdInSidePanel) {
            setVisualizedTask(null);
            return;
        }

        const existingTask = monitoredTasks[taskIdInSidePanel];

        // ALWAYS process SSE events if available (real-time priority)
        if (existingTask?.events?.length > 0) {
            const vizTask = processTaskForVisualization(existingTask.events, monitoredTasks, existingTask);
            setVisualizedTask(vizTask);
        } else if (loadAttemptedRef.current.has(taskIdInSidePanel)) {
            // No SSE events and backend load already attempted — clear stale data
            setVisualizedTask(null);
        }

        // Load from backend ONLY if:
        // 1. No SSE data exists (e.g., page refresh, navigating to historical task), OR
        // 2. Task has reached a terminal state (backfill complete history)
        const isTerminalState = existingTask?.events?.some(e => e.full_payload?.result?.status?.state && ["completed", "failed", "canceled", "rejected"].includes(e.full_payload.result.status.state));

        if ((!existingTask || existingTask.events.length === 0 || isTerminalState) && !loadAttemptedRef.current.has(taskIdInSidePanel)) {
            loadAttemptedRef.current.add(taskIdInSidePanel);
            setIsLoadingTask(true);
            loadTaskFromBackend(taskIdInSidePanel).finally(() => setIsLoadingTask(false));
        }
    }, [taskIdInSidePanel, monitoredTasks, loadTaskFromBackend]);

    // Reset load attempts when task ID changes
    useEffect(() => {
        if (taskIdInSidePanel) {
            const loadAttempted = loadAttemptedRef.current;
            // Clear the load attempt for the previous task when switching to a new one
            // This allows re-loading if the user navigates away and back
            return () => {
                // Don't clear immediately - only clear after a delay to allow for state updates
                setTimeout(() => {
                    loadAttempted.delete(taskIdInSidePanel);
                }, 1000);
            };
        }
    }, [taskIdInSidePanel]);

    // Helper function to determine what to display in the activity panel
    const getActivityPanelContent = () => {
        if (isLoadingTask) {
            return {
                message: "Loading activity data...",
                showButton: false,
            };
        }
        if (isReconnecting || isTaskMonitorConnecting) {
            return {
                message: "Connecting to task monitor ...",
                showButton: false,
            };
        }
        if (!isTaskMonitorConnected) {
            return {
                message: "No connection to task monitor",
                showButton: true,
                buttonText: "Reconnect",
                buttonIcon: RefreshCw,
                buttonAction: connectTaskMonitorStream,
            };
        }

        // isTaskMonitorConnected is true
        if (!taskIdInSidePanel) {
            return {
                message: "No task selected to display",
                showButton: false,
            };
        }

        if (!visualizedTask) {
            return {
                message: "No activity data available for the selected task",
                showButton: false,
            };
        }

        return null;
    };

    const toggleCollapsed = () => {
        const newCollapsed = !isSidePanelCollapsed;
        setIsSidePanelCollapsed(newCollapsed);
        onCollapsedToggle(newCollapsed);
    };

    const handleTabClick = (tab: "files" | "activity" | "rag") => {
        if (tab === "files") {
            setPreviewArtifact(null);
        }

        setActiveSidePanelTab(tab);
    };

    const handleIconClick = (tab: "files" | "activity" | "rag") => {
        if (isSidePanelCollapsed) {
            setIsSidePanelCollapsed(false);
            onCollapsedToggle?.(false);
        }

        handleTabClick(tab);
    };

    // Collapsed state - narrow vertical panel with icons
    if (isSidePanelCollapsed) {
        return (
            <div className="flex h-full w-full flex-col items-center border-l bg-(--background-w10) py-4">
                <Button data-testid="expandPanel" variant="ghost" size="sm" onClick={toggleCollapsed} className="h-10 w-10 p-0" tooltip="Expand Panel">
                    <PanelRightIcon className="size-5" />
                </Button>

                <div className="my-4 h-px w-8 bg-(--secondary-w40)"></div>

                <Button variant="ghost" size="sm" onClick={() => handleIconClick("files")} className="mb-2 h-10 w-10 p-0" tooltip="Files">
                    <FileText className="size-5" />
                </Button>

                <Button variant="ghost" size="sm" onClick={() => handleIconClick("activity")} className={hasSourcesInSession ? "mb-2 h-10 w-10 p-0" : "h-10 w-10 p-0"} tooltip="Activity">
                    <Network className="size-5" />
                </Button>

                {hasSourcesInSession && (
                    <Button variant="ghost" size="sm" onClick={() => handleIconClick("rag")} className="h-10 w-10 p-0" tooltip="Sources">
                        <Link2 className="size-5" />
                    </Button>
                )}
            </div>
        );
    }

    // Expanded state - full panel with tabs
    return (
        <div className="flex h-full flex-col border-l bg-(--background-w10)">
            <div className="m-1 min-h-0 flex-1">
                <Tabs value={activeSidePanelTab} onValueChange={value => handleTabClick(value as "files" | "activity" | "rag")} className="flex h-full flex-col">
                    <div className="@container flex gap-2 p-2">
                        <Button data-testid="collapsePanel" variant="ghost" onClick={toggleCollapsed} className="shrink-0 p-1" tooltip="Collapse Panel">
                            <PanelRightIcon className="size-5" />
                        </Button>
                        <TabsList className="flex min-w-0 flex-1 bg-transparent p-0">
                            <TabsTrigger value="files" title="Files" className="relative min-w-0 flex-1 rounded-none rounded-l-md px-2 data-[state=active]:z-10" onClick={() => setPreviewArtifact(null)}>
                                <FileText className="h-4 w-4 shrink-0" />
                                <span className="ml-1.5 hidden truncate @[240px]:inline">Files</span>
                            </TabsTrigger>
                            <TabsTrigger value="activity" title="Activity" className={`relative min-w-0 flex-1 rounded-none border-x-0 border-y px-2 data-[state=active]:z-10 ${!hasSourcesInSession ? "rounded-r-md border-r" : ""}`}>
                                <Network className="h-4 w-4 shrink-0" />
                                <span className="ml-1.5 hidden truncate @[240px]:inline">Activity</span>
                            </TabsTrigger>
                            {hasSourcesInSession && (
                                <TabsTrigger value="rag" title="Sources" className="relative min-w-0 flex-1 rounded-none rounded-r-md px-2 data-[state=active]:z-10">
                                    <Link2 className="h-4 w-4 shrink-0" />
                                    <span className="ml-1.5 hidden truncate @[240px]:inline">Sources</span>
                                </TabsTrigger>
                            )}
                        </TabsList>
                    </div>
                    <div className="min-h-0 flex-1">
                        <TabsContent value="files" className="m-0 h-full">
                            <div className="h-full">
                                <ArtifactPanel />
                            </div>
                        </TabsContent>

                        <TabsContent value="activity" className="m-0 h-full">
                            <div className="h-full">
                                {(() => {
                                    const emptyStateContent = getActivityPanelContent();

                                    if (!emptyStateContent && visualizedTask) {
                                        return (
                                            <div className="flex h-full flex-col">
                                                <FlowChartDetails task={visualizedTask} />
                                                <FlowChartPanel processedSteps={visualizedTask.steps || []} isRightPanelVisible={false} />
                                            </div>
                                        );
                                    }

                                    return (
                                        <div className="flex h-full items-center justify-center p-4">
                                            <div className="text-center text-(--secondary-text-wMain)">
                                                <Network className="mx-auto mb-4 h-12 w-12" />
                                                <div className="text-lg font-medium">Activity</div>
                                                <div className="mt-2 text-sm">{emptyStateContent?.message}</div>
                                                {emptyStateContent?.showButton && (
                                                    <div className="mt-4">
                                                        <Button onClick={emptyStateContent.buttonAction}>
                                                            {emptyStateContent.buttonIcon &&
                                                                (() => {
                                                                    const ButtonIcon = emptyStateContent.buttonIcon;
                                                                    return <ButtonIcon className="h-4 w-4" />;
                                                                })()}
                                                            {emptyStateContent.buttonText}
                                                        </Button>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })()}
                            </div>
                        </TabsContent>

                        {hasSourcesInSession && (
                            <TabsContent value="rag" className="m-0 h-full">
                                <div className="h-full">
                                    {isProjectIndexingEnabled && hasDocumentSearchResults(ragData) ? <DocumentSourcesPanel ragData={filteredRagData} enabled={ragEnabled} /> : <RAGInfoPanel ragData={filteredRagData} enabled={ragEnabled} />}
                                </div>
                            </TabsContent>
                        )}
                    </div>
                </Tabs>
            </div>
        </div>
    );
};
