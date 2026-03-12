import type { LucideIcon } from "lucide-react";
import type { ExecutableAction, ActionContext } from "./types";
import { executeAgentCommand } from "@/lib/api/agent-assistant";

/**
 * Agent action for executing natural language commands via the UI Assistant agent
 * Tries to call UIAssistant directly first, falls back to chat if agent unavailable
 */
export class AgentAction implements ExecutableAction {
    id: string;
    label: string;
    description?: string;
    keywords?: string[];
    category = "agent";
    icon?: LucideIcon;
    private command: string;

    constructor(config: { id: string; label: string; command: string; description?: string; keywords?: string[]; icon?: LucideIcon }) {
        this.id = config.id;
        this.label = config.label;
        this.command = config.command;
        this.description = config.description;
        this.keywords = config.keywords;
        this.icon = config.icon;
    }

    async execute(context: ActionContext): Promise<void> {
        const { navigate, addNotification } = context;

        console.log("[AgentAction] Executing command:", this.command);

        try {
            // Call UIAssistant agent directly
            console.log("[AgentAction] Calling UIAssistant agent API...");
            const response = await executeAgentCommand(this.command);

            console.log("[AgentAction] Agent response:", response);

            if (!response.success) {
                console.error("[AgentAction] Agent command failed:", response.error);
                if (addNotification) {
                    addNotification(response.error || "Failed to execute command", "warning");
                }
                return;
            }

            // Handle the response action
            if (response.data?.action === "navigate_to_project") {
                console.log("[AgentAction] Navigating to projects page");

                // Show success message
                if (addNotification) {
                    addNotification(response.message || "Project created successfully", "success");
                }

                // Navigate to projects page
                if (navigate) {
                    setTimeout(() => {
                        navigate("/projects");
                    }, 100);
                }
            } else if (response.data?.action === "navigate_to_prompts") {
                console.log("[AgentAction] Navigating to prompts page");

                // Show success message
                if (addNotification) {
                    addNotification(response.message || "Prompt template created successfully", "success");
                }

                // Navigate to prompts library
                if (navigate) {
                    setTimeout(() => {
                        navigate("/prompts");
                    }, 100);
                }
            } else {
                // No specific navigation action, just show the response
                if (addNotification) {
                    addNotification(response.message || "Command executed successfully", "success");
                }
            }
        } catch (error) {
            console.error("[AgentAction] Error calling agent:", error);
            if (addNotification) {
                addNotification(error instanceof Error ? error.message : "An unexpected error occurred", "warning");
            }
        }
    }
}

/**
 * Factory function to create agent actions
 */
export function createAgentAction(config: { id: string; label: string; command: string; description?: string; keywords?: string[]; icon?: LucideIcon }): AgentAction {
    return new AgentAction(config);
}
