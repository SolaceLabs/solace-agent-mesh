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
        const { navigate } = context;

        console.log("[AgentAction] Executing command:", this.command);

        try {
            // Call UIAssistant agent directly
            console.log("[AgentAction] Calling UIAssistant agent API...");
            const response = await executeAgentCommand(this.command);

            console.log("[AgentAction] Agent response:", response);

            if (!response.success) {
                console.error("[AgentAction] Agent command failed:", response.error);
                alert(`Failed to execute command: ${response.error || "Unknown error"}`);
                return;
            }

            // Show success feedback
            console.log("[AgentAction] Command succeeded:", response.message);

            // Handle the response action
            if (response.data?.action === "navigate_to_project") {
                console.log("[AgentAction] Navigating to projects page");
                if (navigate) {
                    // Navigate to projects page so user can see the newly created project
                    navigate("/projects");
                }
                // Show success message
                // TODO: Replace with toast notification when available
                setTimeout(() => {
                    alert(`✓ ${response.message}`);
                }, 200);
            } else {
                // No specific navigation action, just show the response
                alert(response.message);
            }
        } catch (error) {
            console.error("[AgentAction] Error calling agent:", error);
            alert(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
        }
    }
}

/**
 * Factory function to create agent actions
 */
export function createAgentAction(config: { id: string; label: string; command: string; description?: string; keywords?: string[]; icon?: LucideIcon }): AgentAction {
    return new AgentAction(config);
}
