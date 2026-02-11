import { useContext } from "react";

import { SSEContext } from "../contexts";

/**
 * Hook to access the SSE task registry.
 * Use this to register/unregister tasks and query for existing tasks.
 */
export function useSSEContext() {
    const context = useContext(SSEContext);
    if (!context) {
        throw new Error("useSSEContext must be used within SSEProvider");
    }

    return {
        registerTask: context.registerTask,
        unregisterTask: context.unregisterTask,
        getTask: context.getTask,
        getTasks: context.getTasks,
        getTasksByMetadata: context.getTasksByMetadata,
    };
}
