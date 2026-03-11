/**
 * API service for interacting with the UI Assistant agent
 * This agent handles natural language commands from the command palette
 */

import { api } from "@/lib/api";

export interface AgentAssistantRequest {
    query: string;
    user_id?: string;
}

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
 * The agent will interpret the query and perform the appropriate UI action
 */
export const executeAgentCommand = async (query: string): Promise<AgentAssistantResponse> => {
    try {
        // Call the agent via the chat endpoint
        // We'll use the UIAssistant agent specifically
        const response = await api.webui.post("/api/v1/chat", {
            message: query,
            agent_name: "UIAssistant",
            stream: false,
        });

        // Parse the agent's response
        const agentMessage = response.message || response.content || "";

        // Try to extract structured data from the response if available
        let actionData = null;
        if (response.tool_results && response.tool_results.length > 0) {
            // Get data from the first tool result
            const toolResult = response.tool_results[0];
            if (toolResult.data) {
                actionData = toolResult.data;
            }
        }

        return {
            success: true,
            message: agentMessage,
            data: actionData,
        };
    } catch (error) {
        console.error("Agent command execution failed:", error);
        return {
            success: false,
            message: "Failed to execute command",
            error: error instanceof Error ? error.message : String(error),
        };
    }
};
