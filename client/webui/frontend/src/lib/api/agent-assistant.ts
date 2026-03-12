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
 * Wait for task completion by polling the task status endpoint
 */
async function waitForTaskCompletion(taskId: string, sessionId: string | null): Promise<AgentAssistantResponse> {
    const maxAttempts = 60; // 30 seconds with 500ms intervals
    const pollInterval = 500;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            const statusData = await api.webui.get(`/api/v1/tasks/${taskId}/status`);
            console.log("[waitForTaskCompletion] Poll attempt", attempt, "Status:", statusData);

            const task = statusData?.task;

            if (!task) {
                await new Promise(resolve => setTimeout(resolve, pollInterval));
                continue;
            }

            // Check if task is complete
            if (task.status === "completed" || task.status === "failed" || task.status === "cancelled") {
                console.log("[waitForTaskCompletion] Task finished with status:", task.status);

                // Extract response data
                let responseMessage = "";
                let responseData: Record<string, unknown> | null = null;

                // Extract content from task result
                if (task.result_summary) {
                    responseMessage = task.result_summary;
                }

                // Extract tool results if available
                if (task.tool_results && Array.isArray(task.tool_results)) {
                    for (const toolResult of task.tool_results) {
                        if (toolResult.data) {
                            responseData = toolResult.data;
                            // Use tool result message if available
                            if (toolResult.message && !responseMessage) {
                                responseMessage = toolResult.message;
                            }
                        }
                    }
                }

                // Extract from output content if available
                if (!responseMessage && task.output?.content) {
                    responseMessage = task.output.content;
                }

                return {
                    success: task.status === "completed",
                    message: responseMessage || "Command executed successfully",
                    data: responseData || undefined,
                    sessionId: sessionId || undefined,
                };
            }

            // Task still running, wait and poll again
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        } catch (error) {
            console.error("[waitForTaskCompletion] Error polling task status:", error);
            // Continue polling unless it's the last attempt
            if (attempt === maxAttempts - 1) {
                throw error;
            }
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
    }

    throw new Error("Task execution timed out");
}
