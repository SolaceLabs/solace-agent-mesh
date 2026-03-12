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
            // Try to call UIAssistant agent directly
            console.log("[AgentAction] Calling UIAssistant agent API...");
            const response = await executeAgentCommand(this.command);

            console.log("[AgentAction] Agent response:", response);

            if (response.success) {
                // Handle the response action
                if (response.data?.action === "navigate_to_project" && response.data.project_id) {
                    console.log("[AgentAction] Navigating to project:", response.data.project_id);
                    if (navigate) {
                        navigate(`/projects/${response.data.project_id}`);
                    }
                    return;
                }

                // If successful but no navigation action, start chat to show the conversation
                console.log("[AgentAction] Action succeeded but no navigation, starting chat to show response");
                this.startChatSession(context);
                return;
            }

            // Agent call failed, fall back to chat
            console.log("[AgentAction] Agent call failed, falling back to chat:", response.error);
            this.startChatSession(context);
        } catch (error) {
            // If agent doesn't exist or error occurred, fall back to chat
            console.log("[AgentAction] Error calling agent, falling back to chat:", error);
            this.startChatSession(context);
        }
    }

    private startChatSession(context: ActionContext): void {
        const { navigate, startNewChatWithPrompt } = context;

        if (!startNewChatWithPrompt) {
            console.error("[AgentAction] startNewChatWithPrompt function not provided in context");
            return;
        }

        // Navigate to chat page
        if (navigate) {
            navigate("/chat");
        }

        // Start new chat with the command directed to UIAssistant
        startNewChatWithPrompt({
            promptText: this.command,
            groupId: "agent-command-auto-submit",
            groupName: "Agent Command",
        });
    }
}

/**
 * Factory function to create agent actions
 */
export function createAgentAction(config: { id: string; label: string; command: string; description?: string; keywords?: string[]; icon?: LucideIcon }): AgentAction {
    return new AgentAction(config);
}
