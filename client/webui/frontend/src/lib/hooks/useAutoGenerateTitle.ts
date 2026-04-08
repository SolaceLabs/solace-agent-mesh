import { useCallback } from "react";

import { api } from "@/lib/api";
import { useIsAutoTitleGenerationEnabled } from "@/lib/hooks/useIsAutoTitleGenerationEnabled";
import { useTitleGeneration } from "@/lib/hooks/useTitleGeneration";

interface BackgroundTask {
    taskId: string;
    sessionId?: string;
}

// Module-scoped so state survives component re-mounts
const generatedSessions = new Set<string>();

/**
 * Encapsulates auto title generation logic: feature flag check, session deduplication,
 * and two generation paths (from provided text or from task API lookup).
 */
export function useAutoGenerateTitle() {
    const autoTitleGenerationEnabled = useIsAutoTitleGenerationEnabled();
    const { generateTitle } = useTitleGeneration();

    /**
     * Generate a title for a session if auto-generation is enabled and
     * a title hasn't already been generated for this session.
     */
    const autoGenerateTitle = useCallback(
        async (sessionId: string, userText: string, agentText: string): Promise<void> => {
            if (!autoTitleGenerationEnabled) return;
            if (!sessionId || generatedSessions.has(sessionId)) return;
            if (!userText || !agentText) return;

            generatedSessions.add(sessionId);
            try {
                await generateTitle(sessionId, userText, agentText);
            } catch (error) {
                console.error("[useAutoTitleGeneration] Title generation failed:", error);
            }
        },
        [autoTitleGenerationEnabled, generateTitle]
    );

    /**
     * Generate a title for a completed background task. Resolves the session ID
     * from the task (falling back to an API lookup) and fetches the title data
     * from the backend.
     */
    const autoGenerateTitleForTask = useCallback(
        async (taskId: string, backgroundTasks: BackgroundTask[]): Promise<void> => {
            if (!autoTitleGenerationEnabled) return;

            // Resolve session ID from task list or API
            const bgTask = backgroundTasks.find(t => t.taskId === taskId);
            let taskSessionId = bgTask?.sessionId;

            if (!taskSessionId || taskSessionId.trim() === "") {
                try {
                    const statusData = await api.webui.get(`/api/v1/tasks/${taskId}/status`);
                    taskSessionId = statusData?.task?.context_id || statusData?.task?.contextId;
                } catch {
                    // Title generation will be skipped if session ID cannot be determined
                    return;
                }
            }

            if (!taskSessionId || taskSessionId.trim() === "" || generatedSessions.has(taskSessionId)) {
                return;
            }

            generatedSessions.add(taskSessionId);

            try {
                const titleData = await api.webui.get(`/api/v1/tasks/${taskId}/title-data`);
                const userMessageText = titleData?.user_message || "";
                const agentResponseText = titleData?.agent_response || "";

                if (userMessageText && agentResponseText) {
                    await generateTitle(taskSessionId, userMessageText, agentResponseText);
                }
            } catch (error) {
                console.error("[useAutoTitleGeneration] Error generating title for task:", error);
            }
        },
        [autoTitleGenerationEnabled, generateTitle]
    );

    return {
        autoTitleGenerationEnabled,
        autoGenerateTitle,
        autoGenerateTitleForTask,
    };
}
