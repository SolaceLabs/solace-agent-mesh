import React, { type FormEvent, useMemo } from "react";

import { Pencil, BookOpen, Code2, Lightbulb, Sparkles } from "lucide-react";

import { SolaceIcon } from "@/lib/components/common";
import { useChatContext, useConfigContext } from "@/lib/hooks";
import type { AgentCardInfo, WelcomeSuggestion } from "@/lib/types";
import { ChatInputArea } from "./ChatInputArea";
import { CHAT_STYLES } from "@/lib/components/ui/chat/chatStyles";

interface SuggestionChip {
    label: string;
    icon: React.ReactNode;
    prompt: string;
    autoSend?: boolean;
}

// Use \u00A0 (non-breaking space) at the end so the browser doesn't collapse the trailing space
// when the contenteditable input renders it as innerHTML
const DEFAULT_SUGGESTIONS: SuggestionChip[] = [
    {
        label: "Write",
        icon: <Pencil className="h-4 w-4" />,
        prompt: "Help me write\u00A0",
    },
    {
        label: "Learn",
        icon: <BookOpen className="h-4 w-4" />,
        prompt: "Explain to me\u00A0",
    },
    {
        label: "Code",
        icon: <Code2 className="h-4 w-4" />,
        prompt: "Help me build\u00A0",
    },
    {
        label: "Brainstorm",
        icon: <Lightbulb className="h-4 w-4" />,
        prompt: "Help me brainstorm ideas for\u00A0",
    },
    {
        label: "Surprise me",
        icon: <Sparkles className="h-4 w-4" />,
        prompt: "Surprise me with something interesting and useful",
        autoSend: true,
    },
];

/** Convert agent-provided WelcomeSuggestions to SuggestionChips. */
const toChips = (suggestions: WelcomeSuggestion[]): SuggestionChip[] =>
    suggestions.map((s) => ({
        label: s.label,
        icon: <Sparkles className="h-4 w-4" />,
        prompt: s.prompt,
        autoSend: s.auto_send,
    }));

interface ChatWelcomeScreenProps {
    agents: AgentCardInfo[];
    selectedAgentName?: string;
}

export const ChatWelcomeScreen: React.FC<ChatWelcomeScreenProps> = ({ agents, selectedAgentName }) => {
    const { handleSubmit } = useChatContext();
    const { configBotName } = useConfigContext();

    const botName = configBotName || "SAM";

    // Use the selected agent's welcome config if available.
    const welcomeAgent = useMemo(
        () => agents.find((a) => a.name === selectedAgentName),
        [agents, selectedAgentName],
    );

    const welcomeMessage = welcomeAgent?.welcome?.welcome_message;
    // For agents without a welcome config, use a generic greeting with their name
    const defaultHeading = welcomeAgent
        ? `Hi, I'm ${welcomeAgent.displayName || welcomeAgent.name}. How can I help you?`
        : `What can ${botName} help you with?`;
    const suggestions = useMemo(
        () => (welcomeAgent?.welcome?.suggestions ? toChips(welcomeAgent.welcome.suggestions) : DEFAULT_SUGGESTIONS),
        [welcomeAgent],
    );

    const handleChipClick = async (chip: SuggestionChip) => {
        if (chip.autoSend) {
            const fakeEvent = new Event("submit") as unknown as FormEvent;
            await handleSubmit(fakeEvent, [], chip.prompt);
        } else {
            // Set the input text and let the user edit before sending
            window.dispatchEvent(
                new CustomEvent("set-chat-input", {
                    detail: { text: chip.prompt },
                })
            );
        }
    };

    return (
        <div className="flex h-full w-full flex-col">
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4">
                <div className="flex flex-col items-center gap-6" style={{ maxWidth: "640px" }}>
                    <SolaceIcon variant="short" className="h-12 w-12 opacity-80" />
                    <h1 className="text-foreground text-center text-3xl font-semibold tracking-tight">
                        {welcomeMessage || defaultHeading}
                    </h1>
                    <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
                        {suggestions.map((chip) => (
                            <button
                                key={chip.label}
                                onClick={() => handleChipClick(chip)}
                                className="border-border bg-background hover:bg-accent text-foreground flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors"
                            >
                                {chip.icon}
                                {chip.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            <div style={CHAT_STYLES} className="pb-6">
                <ChatInputArea agents={agents} />
            </div>
        </div>
    );
};
