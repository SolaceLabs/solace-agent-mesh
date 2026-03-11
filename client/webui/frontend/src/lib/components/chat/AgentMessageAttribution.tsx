/**
 * Agent Message Attribution Component
 *
 * Displays agent identification above agent messages in collaborative chats
 * Shows agent icon and "Solace Agent Mesh" label
 */

import { Bot } from "lucide-react";

interface AgentMessageAttributionProps {
    /** Agent name to display */
    readonly agentName?: string;
}

export function AgentMessageAttribution({ agentName = "Agent" }: AgentMessageAttributionProps) {
    return (
        <div className="flex items-center gap-2 pb-1">
            {/* Agent icon - matches AgentNode styling */}
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-(--color-accent-n2-w10) dark:bg-(--color-accent-n2-w100)">
                <Bot className="h-4 w-4 text-(--color-brand-wMain)" />
            </div>

            {/* Agent name */}
            <span className="text-sm font-medium">{agentName}</span>
        </div>
    );
}
