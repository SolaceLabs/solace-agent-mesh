import type { LucideIcon } from "lucide-react";
import type { ExecutableAction, ActionContext } from "./types";

/**
 * Chat action for starting a new chat session with a specific prompt
 */
export class ChatAction implements ExecutableAction {
    id: string;
    label: string;
    description?: string;
    keywords?: string[];
    category = "chat";
    icon?: LucideIcon;
    private prompt: string;

    constructor(config: { id: string; label: string; prompt: string; description?: string; keywords?: string[]; icon?: LucideIcon }) {
        this.id = config.id;
        this.label = config.label;
        this.prompt = config.prompt;
        this.description = config.description;
        this.keywords = config.keywords;
        this.icon = config.icon;
    }

    execute(context: ActionContext): void {
        const { startNewChatWithPrompt, navigate } = context;

        if (!startNewChatWithPrompt) {
            console.error("startNewChatWithPrompt function not provided in context");
            return;
        }

        // Navigate to chat page first
        if (navigate) {
            navigate("/chat");
        }

        // Start new chat with the prompt and auto-submit
        // The groupId "command-palette-auto-submit" signals ChatInputArea to auto-submit
        startNewChatWithPrompt({
            promptText: this.prompt,
            groupId: "command-palette-auto-submit",
            groupName: "Command Palette",
        });
    }
}

/**
 * Factory function to create chat actions
 */
export function createChatAction(config: { id: string; label: string; prompt: string; description?: string; keywords?: string[]; icon?: LucideIcon }): ChatAction {
    return new ChatAction(config);
}
