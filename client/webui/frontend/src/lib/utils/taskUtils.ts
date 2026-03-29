import type { RAGSearchResult } from "@/lib/types";

interface TaskWithMetadata {
    taskId?: string;
    id?: string;
    workflowTaskId?: string;
    taskMetadata?: { rag_data?: unknown[]; [key: string]: unknown } | string | null;
}

/**
 * Parse taskMetadata from string or object form.
 * Backend may store it as a JSON string; this normalises to an object or null.
 */
export function parseTaskMetadata(raw: unknown): Record<string, unknown> | null {
    if (!raw) return null;
    if (typeof raw === "object") return raw as Record<string, unknown>;
    if (typeof raw === "string") {
        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }
    return null;
}

/**
 * Extract RAG search results from an array of tasks.
 *
 * Works with both ChatProvider's parsed tasks (taskId, taskMetadata as object)
 * and shared-session tasks (workflowTaskId/id, taskMetadata as string|object).
 */
export function extractRagDataFromTasks(tasks: TaskWithMetadata[]): RAGSearchResult[] {
    const allRagData: RAGSearchResult[] = [];

    for (const task of tasks) {
        const taskId = task.workflowTaskId || task.taskId || task.id || "";
        const metadata = parseTaskMetadata(task.taskMetadata);

        if (metadata && Array.isArray(metadata.rag_data)) {
            for (const ragEntry of metadata.rag_data) {
                allRagData.push({
                    ...(ragEntry as RAGSearchResult),
                    taskId,
                });
            }
        }
    }

    return allRagData;
}
