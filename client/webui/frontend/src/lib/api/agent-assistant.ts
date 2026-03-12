/**
 * API service for interacting with the UI Assistant agent
 * This agent handles natural language commands from the command palette
 */

import { api } from "@/lib/api";
import { v4 as uuidv4 } from "uuid";

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
    sessionId?: string;
}

interface Message {
    role: string;
    parts: Array<{ kind: string; text: string }>;
    messageId: string;
    kind: string;
    contextId?: string | null;
    metadata: {
        agent_name: string;
    };
}

interface SendStreamingMessageRequest {
    jsonrpc: string;
    id: string;
    method: string;
    params: {
        message: Message;
    };
}

/**
 * Send a natural language query to the UI Assistant agent
 * Uses the /message:stream endpoint to execute commands and receive responses
 */
export const executeAgentCommand = async (query: string): Promise<AgentAssistantResponse> => {
    try {
        console.log("[executeAgentCommand] Executing command via UIAssistant:", query);

        // Build the A2A message
        const a2aMessage: Message = {
            role: "user",
            parts: [{ kind: "text", text: query }],
            messageId: `msg-${uuidv4()}`,
            kind: "message",
            contextId: null, // null/empty creates new session
            metadata: {
                agent_name: "UIAssistant",
            },
        };

        // Build the JSON-RPC request
        const sendMessageRequest: SendStreamingMessageRequest = {
            jsonrpc: "2.0",
            id: `req-${uuidv4()}`,
            method: "message/stream",
            params: {
                message: a2aMessage,
            },
        };

        console.log("[executeAgentCommand] Sending request to /api/v1/message:stream");

        // Send the request
        const result = await api.webui.post("/api/v1/message:stream", sendMessageRequest);

        const task = result?.result;
        const sessionId = task?.contextId;

        if (!task?.id) {
            throw new Error("Backend did not return a valid task ID");
        }

        console.log("[executeAgentCommand] Task created:", task.id, "Session:", sessionId);

        // Wait for task completion and collect results
        const response = await waitForTaskCompletion(task.id, sessionId);

        // Clean up session after execution
        if (sessionId) {
            try {
                await api.webui.delete(`/api/v1/sessions/${sessionId}`);
                console.log("[executeAgentCommand] Cleaned up session:", sessionId);
            } catch (cleanupError) {
                console.warn("[executeAgentCommand] Failed to cleanup session:", cleanupError);
            }
        }

        return response;
    } catch (error) {
        console.error("[executeAgentCommand] Error:", error);
        return {
            success: false,
            message: "Failed to execute command",
            error: error instanceof Error ? error.message : String(error),
        };
    }
};

/**
 * Wait for task completion and extract the agent's response
 */
async function waitForTaskCompletion(taskId: string, sessionId: string | null): Promise<AgentAssistantResponse> {
    return new Promise((resolve, reject) => {
        let responseMessage = "";
        let responseData: Record<string, unknown> | null = null;
        let hasError = false;

        // Connect to task status stream
        const sseUrl = `/api/v1/tasks/${taskId}/status/stream`;
        const fullSseUrl = api.webui.getFullUrl(sseUrl);
        const eventSource = new EventSource(fullSseUrl);

        const timeout = setTimeout(() => {
            eventSource.close();
            reject(new Error("Agent command execution timed out"));
        }, 30000);

        eventSource.onmessage = event => {
            try {
                const data = JSON.parse(event.data);
                console.log("[waitForTaskCompletion] SSE event:", data);

                // Extract content from status updates
                if (data.result?.status?.content) {
                    responseMessage += data.result.status.content;
                }

                // Extract tool results
                if (data.result?.status?.tool_results) {
                    for (const toolResult of data.result.status.tool_results) {
                        if (toolResult.data) {
                            responseData = toolResult.data;
                        }
                    }
                }

                // Check for completion
                if (data.result?.kind === "completed" || data.result?.kind === "failed") {
                    clearTimeout(timeout);
                    eventSource.close();

                    if (data.result.kind === "failed") {
                        hasError = true;
                    }

                    resolve({
                        success: !hasError,
                        message: responseMessage || "Command executed successfully",
                        data: responseData || undefined,
                        sessionId: sessionId || undefined,
                    });
                }
            } catch (parseError) {
                console.error("[waitForTaskCompletion] Error parsing SSE event:", parseError);
            }
        };

        eventSource.onerror = error => {
            console.error("[waitForTaskCompletion] SSE error:", error);
            clearTimeout(timeout);
            eventSource.close();
            reject(new Error("Connection to agent failed"));
        };
    });
}
