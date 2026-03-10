import React, { type FormEvent } from "react";

import { Pencil, BookOpen, Code2, Lightbulb, Sparkles } from "lucide-react";

import { SolaceIcon } from "@/lib/components/common";
import { useChatContext, useConfigContext } from "@/lib/hooks";
import type { AgentCardInfo } from "@/lib/types";
import { ChatInputArea } from "./ChatInputArea";
import { CHAT_STYLES } from "@/lib/components/ui/chat/chatStyles";

interface SuggestionChip {
    label: string;
    icon: React.ReactNode;
    prompt: string;
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
    },
];

interface ChatWelcomeScreenProps {
    agents: AgentCardInfo[];
}

export const ChatWelcomeScreen: React.FC<ChatWelcomeScreenProps> = ({ agents }) => {
    const { handleSubmit } = useChatContext();
    const { configBotName } = useConfigContext();

    const botName = configBotName || "SAM";

    const handleChipClick = async (chip: SuggestionChip) => {
        if (chip.label === "Surprise me") {
            const fakeEvent = new Event("submit") as unknown as FormEvent;
            await handleSubmit(fakeEvent, [], chip.prompt);
        } else {
            // For other chips, dispatch a custom event to set the input text and focus
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
                        What can {botName} help you with?
                    </h1>
                    <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
                        {DEFAULT_SUGGESTIONS.map((chip) => (
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
