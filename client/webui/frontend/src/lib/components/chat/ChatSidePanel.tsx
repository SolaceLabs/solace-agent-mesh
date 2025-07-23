import React, { useState, useEffect } from "react";

import { Menu, FileText, Network } from "lucide-react";

import { Button, Tabs, TabsList, TabsTrigger, TabsContent } from "@/lib/components/ui";
import { useTaskContext, useChatContext } from "@/lib/hooks";
import { FlowChartPanel, processTaskForVisualization } from "@/lib/components/activities";
import type { VisualizedTask } from "@/lib/types";

import { ArtifactPanel } from "./artifact/ArtifactPanel";

interface ChatSidePanelProps {
    onCollapsedToggle: (isSidePanelCollapsed: boolean) => void;
    isSidePanelCollapsed: boolean;
    setIsSidePanelCollapsed: (isSidePanelCollapsed: boolean) => void;
    isSidePanelTransitioning: boolean;
}

export const ChatSidePanel: React.FC<ChatSidePanelProps> = ({ onCollapsedToggle, isSidePanelCollapsed, setIsSidePanelCollapsed, isSidePanelTransitioning }) => {
    const { activeSidePanelTab, setActiveSidePanelTab, taskIdInSidePanel } = useChatContext();
    const { monitoredTasks } = useTaskContext();
    const [visualizedTask, setVisualizedTask] = useState<VisualizedTask | null>(null);

    // Process task data for visualization when the selected workflow task ID changes
    useEffect(() => {
        if (taskIdInSidePanel && monitoredTasks[taskIdInSidePanel]) {
            const taskDetails = monitoredTasks[taskIdInSidePanel];
            const vizTask = processTaskForVisualization(taskDetails.events || [], monitoredTasks, taskDetails);
            setVisualizedTask(vizTask);
        } else {
            setVisualizedTask(null);
        }
    }, [taskIdInSidePanel, monitoredTasks]);

    const toggleCollapsed = () => {
        const newCollapsed = !isSidePanelCollapsed;
        setIsSidePanelCollapsed(newCollapsed);
        onCollapsedToggle(newCollapsed);
    };

    const handleIconClick = (tab: "files" | "workflow") => {
        if (isSidePanelCollapsed) {
            setIsSidePanelCollapsed(false);
            setActiveSidePanelTab(tab);
            onCollapsedToggle?.(false);
        } else {
            setActiveSidePanelTab(tab);
        }
    };

    // Collapsed state - narrow vertical panel with icons
    if (isSidePanelCollapsed) {
        return (
            <div className="bg-background flex h-full w-full flex-col items-center border-l py-4">
                <Button variant="ghost" size="sm" onClick={toggleCollapsed} className="h-10 w-10 p-0" tooltip="Expand Panel">
                    <Menu className="h-5 w-5" />
                </Button>

                <div className="bg-border my-4 h-px w-8"></div>

                <Button variant="ghost" size="sm" onClick={() => handleIconClick("files")} className="mb-2 h-10 w-10 p-0" tooltip="Files">
                    <FileText className="h-5 w-5" />
                </Button>

                <Button variant="ghost" size="sm" onClick={() => handleIconClick("workflow")} className="h-10 w-10 p-0" tooltip="Workflow">
                    <Network className="h-5 w-5" />
                </Button>
            </div>
        );
    }

    // Expanded state - full panel with tabs
    return (
        <div className="bg-background flex h-full flex-col border-l">
            {/* Tabs */}
            <div className="m-1 min-h-0 flex-1">
                <Tabs value={activeSidePanelTab} onValueChange={value => setActiveSidePanelTab(value as "files" | "workflow")} className="flex h-full flex-col">
                    {/* Tab List */}
                    <div className="p-2 flex gap-2">
                        <Button variant="ghost" onClick={toggleCollapsed} className="p-1" tooltip="Collapse Panel">
                            <Menu className="h-5 w-5" />
                        </Button>
                        <TabsList className="grid w-full grid-cols-2 bg-transparent p-0">
                            <TabsTrigger value="files" className="border-border bg-muted data-[state=active]:bg-background relative cursor-pointer rounded-none rounded-l-md border border-r-0 data-[state=active]:z-10 data-[state=active]:border-r-0">
                                <FileText className="mr-2 h-4 w-4" />
                                Files
                            </TabsTrigger>
                            <TabsTrigger
                                value="workflow"
                                className="border-border bg-muted data-[state=active]:bg-background relative cursor-pointer rounded-none rounded-r-md border border-l-0 data-[state=active]:z-10 data-[state=active]:border-l-0"
                            >
                                <Network className="mr-2 h-4 w-4" />
                                Workflow
                            </TabsTrigger>
                        </TabsList>
                    </div>

                    {/* Tab Content */}
                    <div className="min-h-0 flex-1">
                        <TabsContent value="files" className="m-0 h-full">
                            <div className="h-full">
                                <ArtifactPanel />
                            </div>
                        </TabsContent>

                        <TabsContent value="workflow" className="m-0 h-full">
                            <div className="h-full">
                                {visualizedTask ? (
                                    <FlowChartPanel processedSteps={visualizedTask.steps || []} isRightPanelVisible={false} isSidePanelTransitioning={isSidePanelTransitioning} />
                                ) : (
                                    <div className="flex h-full items-center justify-center p-4">
                                        <div className="text-muted-foreground text-center">
                                            <Network className="mx-auto mb-4 h-12 w-12" />
                                            <div className="text-lg font-medium">Workflow</div>
                                            <div className="mt-2 text-sm">{taskIdInSidePanel ? "Loading workflow data..." : "No task selected to display"}</div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </TabsContent>
                    </div>
                </Tabs>
            </div>
        </div>
    );
};
