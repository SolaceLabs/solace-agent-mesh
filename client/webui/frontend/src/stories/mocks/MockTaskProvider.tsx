import { TaskContext, type TaskContextValue } from "@/lib/contexts/TaskContext";
import React from "react";

// Default mock values for TaskContext
const defaultMockTaskContext: TaskContextValue = {
    // State
    isTaskMonitorConnecting: false,
    isTaskMonitorConnected: true,
    taskMonitorSseError: null,
    monitoredTasks: {},
    monitoredTaskOrder: [],
    highlightedStepId: null,
    isReconnecting: false,
    reconnectionAttempts: 0,

    // Actions
    connectTaskMonitorStream: async () => {},
    disconnectTaskMonitorStream: async () => {},
    setHighlightedStepId: () => {},
    loadTaskFromBackend: async () => null,
    registerTaskEarly: () => {},
};

interface MockTaskProviderProps {
    children: React.ReactNode;
    mockValues?: Partial<TaskContextValue>;
}

export const MockTaskProvider: React.FC<MockTaskProviderProps> = ({ children, mockValues = {} }) => {
    const contextValue = {
        ...defaultMockTaskContext,
        ...mockValues,
    };

    return <TaskContext.Provider value={contextValue}>{children}</TaskContext.Provider>;
};
