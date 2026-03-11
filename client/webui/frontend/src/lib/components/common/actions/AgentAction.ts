import type { LucideIcon } from "lucide-react";
import type { ExecutableAction, ActionContext } from "./types";
import { executeAgentCommand } from "@/lib/api/agent-assistant";

/**
 * Agent action for executing natural language commands via the UI Assistant agent
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

        try {
            // Execute the command via the UI Assistant agent
            const response = await executeAgentCommand(this.command);

            if (!response.success) {
                console.error("Agent command failed:", response.error);
                // Could show an error toast here
                return;
            }

            // Handle the response action
            if (response.data?.action === "navigate_to_project" && response.data.project_id) {
                // Navigate to the newly created project
                if (navigate) {
                    navigate(`/projects/${response.data.project_id}`);
                }
            }

            // Could show a success toast with response.message here
            console.log("Agent command succeeded:", response.message);
        } catch (error) {
            console.error("Error executing agent command:", error);
        }
    }
}

/**
 * Factory function to create agent actions
 */
export function createAgentAction(config: { id: string; label: string; command: string; description?: string; keywords?: string[]; icon?: LucideIcon }): AgentAction {
    return new AgentAction(config);
}
