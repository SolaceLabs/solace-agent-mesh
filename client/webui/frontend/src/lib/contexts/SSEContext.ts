import { createContext } from "react";

import type { SSETask } from "../types";

export interface SSEContextValue {
    registerTask: (task: Omit<SSETask, "registeredAt">) => void;
    unregisterTask: (taskId: string) => void;
    getTask: (taskId: string) => SSETask | null;
    getTasks: () => SSETask[];
    getTasksByMetadata: (key: string, value: unknown) => SSETask[];
}

export const SSEContext = createContext<SSEContextValue | null>(null);
