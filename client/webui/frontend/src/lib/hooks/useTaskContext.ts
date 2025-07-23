import { useContext } from "react";

import { TaskContext } from "@/lib/contexts/TaskContext";
import type { TaskContextValue } from "@/lib/contexts/TaskContext";

export const useTaskContext = (): TaskContextValue => {
    const context = useContext(TaskContext);
    if (context === undefined) {
        throw new Error("useTaskContext must be used within a TaskProvider");
    }
    return context;
};
