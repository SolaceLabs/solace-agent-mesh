import { useState, useCallback, type Dispatch, type SetStateAction } from "react";

export interface SidePanelState {
    isCollapsed: boolean;
    activeTab: "files" | "workflow";
    taskId: string | null;
}

interface UseSidePanelOptions {
    defaultTab?: "files" | "workflow";
    defaultCollapsed?: boolean;
}

interface UseSidePanelReturn {
    isCollapsed: boolean;
    activeTab: "files" | "workflow";
    taskId: string | null;
    setCollapsed: Dispatch<SetStateAction<boolean>>;
    setActiveTab: Dispatch<SetStateAction<"files" | "workflow">>;
    setTaskId: Dispatch<SetStateAction<string | null>>;
    openTab: (tab: "files" | "workflow") => void;
}

/**
 * Custom hook to manage side panel UI state
 * Handles panel collapse/expand, active tab selection, and task ID for workflow visualization
 */
export const useSidePanel = ({ defaultTab = "files", defaultCollapsed = true }: UseSidePanelOptions = {}): UseSidePanelReturn => {
    const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
    const [activeTab, setActiveTab] = useState<"files" | "workflow">(defaultTab);
    const [taskId, setTaskId] = useState<string | null>(null);

    /**
     * Open the side panel to a specific tab
     * Also dispatches a custom event for components that need to know
     */
    const openTab = useCallback((tab: "files" | "workflow") => {
        setIsCollapsed(false);
        setActiveTab(tab);

        // Dispatch event for other components (e.g., ChatInputArea)
        if (typeof window !== "undefined") {
            window.dispatchEvent(
                new CustomEvent("expand-side-panel", {
                    detail: { tab },
                })
            );
        }
    }, []);

    return {
        isCollapsed,
        activeTab,
        taskId,
        setCollapsed: setIsCollapsed,
        setActiveTab,
        setTaskId,
        openTab,
    };
};
