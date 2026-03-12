/**
 * API service for interacting with the UI Assistant agent
 * This agent handles natural language commands from the command palette
 */

import { api } from "@/lib/api";

export interface AgentAssistantResponse {
    success: boolean;
    message: string;
    data?: {
        action?: string;
        project_id?: string;
        project_name?: string;
        [key: string]: unknown;
    };
    error?: string;
}

/**
 * Send a natural language query to the UI Assistant agent
 * Creates a temporary session, sends the command, waits for response, and cleans up
 */
export const executeAgentCommand = async (query: string): Promise<AgentAssistantResponse> => {
    let sessionId: string | null = null;

    try {
        console.log("[executeAgentCommand] Creating temporary session for UIAssistant");

        // Create a new temporary session for UIAssistant
        const sessionResponse = await api.webui.post("/api/v1/sessions", {
            agent_name: "UIAssistant",
        });

        sessionId = sessionResponse.id;
        console.log("[executeAgentCommand] Created session:", sessionId);

        // Subscribe to SSE stream to receive agent responses
        const sseUrl = `/api/v1/sessions/${sessionId}/stream`;
        const fullSseUrl = api.webui.getFullUrl(sseUrl);

        const result = await new Promise<AgentAssistantResponse>((resolve, reject) => {
            let eventSource: EventSource | null = null;
            let responseMessage = "";
            let responseData: Record<string, unknown> | null = null;
            let hasError = false;

            eventSource = new EventSource(fullSseUrl);

            const timeout = setTimeout(() => {
                eventSource?.close();
                reject(new Error("Agent command execution timed out"));
            }, 30000); // 30 second timeout

            eventSource.onmessage = event => {
                try {
                    const data = JSON.parse(event.data);
                    console.log("[executeAgentCommand] SSE event:", data);

                    // Handle agent response content
                    if (data.type === "content" && data.content) {
                        responseMessage += data.content;
                    }

                    // Handle tool results
                    if (data.type === "tool_result" && data.tool_result?.data) {
                        responseData = data.tool_result.data;
                    }

                    // Handle completion
                    if (data.type === "done" || data.type === "complete") {
                        clearTimeout(timeout);
                        eventSource?.close();

                        resolve({
                            success: !hasError,
                            message: responseMessage || "Command executed successfully",
                            data: responseData || undefined,
                        });
                    }

                    // Handle errors
                    if (data.type === "error") {
                        hasError = true;
                        responseMessage = data.error || "An error occurred";
                    }
                } catch (parseError) {
                    console.error("[executeAgentCommand] Error parsing SSE event:", parseError);
                }
            };

            eventSource.onerror = error => {
                console.error("[executeAgentCommand] SSE error:", error);
                clearTimeout(timeout);
                eventSource?.close();
                reject(new Error("Connection to agent failed"));
            };

            // Send the command message after a short delay to ensure SSE is connected
            setTimeout(async () => {
                try {
                    console.log("[executeAgentCommand] Sending message:", query);
                    await api.webui.post(`/api/v1/sessions/${sessionId}/messages`, {
                        content: query,
                        role: "user",
                    });
                } catch (sendError) {
                    clearTimeout(timeout);
                    eventSource?.close();
                    reject(sendError);
                }
            }, 100);
        });

        // Clean up session after successful execution
        if (sessionId) {
            try {
                await api.webui.delete(`/api/v1/sessions/${sessionId}`);
                console.log("[executeAgentCommand] Cleaned up session:", sessionId);
            } catch (cleanupError) {
                console.warn("[executeAgentCommand] Failed to cleanup session:", cleanupError);
            }
        }

        return result;
    } catch (error) {
        console.error("[executeAgentCommand] Error:", error);

        // Clean up session on error
        if (sessionId) {
            try {
                await api.webui.delete(`/api/v1/sessions/${sessionId}`);
            } catch (cleanupError) {
                console.warn("[executeAgentCommand] Failed to cleanup session:", cleanupError);
            }
        }

        return {
            success: false,
            message: "Failed to execute command",
            error: error instanceof Error ? error.message : String(error),
        };
    }
};
