/**
 * Displays a popover with searchable prompt library when "/" is typed
 * Also handles reserved commands like /create-template
 */

import React, { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, NotepadText, Plus } from "lucide-react";
import type { MessageFE, PromptGroup } from "@/lib/types";
import { detectVariables } from "@/lib/utils/promptUtils";
import { VariableDialog } from "./VariableDialog";
import { fetchJsonWithError } from "@/lib/utils/api";

export type ChatCommand = "create-template";

interface ReservedCommand {
    command: ChatCommand;
    name: string;
    description: string;
    icon: typeof NotepadText;
}

const RESERVED_COMMANDS: ReservedCommand[] = [
    {
        command: "create-template",
        name: "Create Template from Session",
        description: "Create a reusable prompt template from this conversation",
        icon: NotepadText,
    },
];

interface PromptsCommandProps {
    isOpen: boolean;
    onClose: () => void;
    textAreaRef: React.RefObject<HTMLTextAreaElement | null>;
    onPromptSelect: (promptText: string) => void;
    messages?: MessageFE[];
    onReservedCommand?: (command: ChatCommand, context?: string) => void;
}

export const PromptsCommand: React.FC<PromptsCommandProps> = ({ isOpen, onClose, textAreaRef, onPromptSelect, messages = [], onReservedCommand }) => {
    const navigate = useNavigate();
    const [searchValue, setSearchValue] = useState("");
    const [activeIndex, setActiveIndex] = useState(0);
    const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedGroup, setSelectedGroup] = useState<PromptGroup | null>(null);
    const [showVariableDialog, setShowVariableDialog] = useState(false);
    const [isKeyboardMode, setIsKeyboardMode] = useState(false);

    const inputRef = useRef<HTMLInputElement>(null);
    const popoverRef = useRef<HTMLDivElement>(null);
    const backdropRef = useRef<HTMLDivElement>(null);

    // Fetch prompt groups when opened
    useEffect(() => {
        if (!isOpen) return;

        const fetchPromptGroups = async () => {
            setIsLoading(true);
            try {
                const data = await fetchJsonWithError("/api/v1/prompts/groups/all");
                setPromptGroups(data);
            } catch (error) {
                console.error("Failed to fetch prompt groups:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPromptGroups();
    }, [isOpen]);

    // Reserved commands - always shown (not filtered), only check availability
    const availableReservedCommands = useMemo(() => {
        // Only show create-template if there are user messages in the session
        const hasUserMessages = messages.some(m => m.isUser && !m.isStatusBubble);
        return RESERVED_COMMANDS.filter(cmd => {
            if (cmd.command === "create-template") {
                return hasUserMessages;
            }
            return true;
        });
    }, [messages]);

    // Filter prompt groups based on search
    const filteredGroups = useMemo(() => {
        if (!searchValue) return promptGroups;

        const search = searchValue.toLowerCase();
        return promptGroups.filter(group => group.name.toLowerCase().includes(search) || group.description?.toLowerCase().includes(search) || group.command?.toLowerCase().includes(search) || group.category?.toLowerCase().includes(search));
    }, [promptGroups, searchValue]);

    // Combine prompts and reserved commands for display (reserved at bottom)
    const allItems = useMemo(() => {
        return [...filteredGroups, ...availableReservedCommands];
    }, [filteredGroups, availableReservedCommands]);

    // Format session history for context
    const formatSessionHistory = useCallback((messages: MessageFE[]): string => {
        return messages
            .filter(m => !m.isStatusBubble && !m.isError && !m.authenticationLink)
            .map(m => {
                const role = m.isUser ? "User" : "Assistant";
                const text =
                    m.parts
                        ?.filter(p => p.kind === "text")
                        .map(p => (p as { text: string }).text)
                        .join("\n") || "";
                return `${role}: ${text}`;
            })
            .join("\n\n");
    }, []);

    // Handle reserved command selection
    const handleReservedCommandSelect = useCallback(
        (cmd: ReservedCommand) => {
            if (cmd.command === "create-template" && onReservedCommand) {
                const sessionHistory = formatSessionHistory(messages);
                onReservedCommand(cmd.command, sessionHistory);
                onClose();
                setSearchValue("");
            }
        },
        [messages, formatSessionHistory, onReservedCommand, onClose]
    );

    // Handle navigation to Prompts area
    const handleNavigateToPrompts = useCallback(() => {
        onClose();
        setSearchValue("");
        // Navigate to prompts page with AI-assisted mode
        navigate("/prompts/new?mode=ai-assisted");
    }, [onClose, navigate]);

    // Handle prompt selection
    const handlePromptSelect = useCallback(
        (group: PromptGroup) => {
            const promptText = group.productionPrompt?.promptText || "";

            // Check for variables
            const variables = detectVariables(promptText);
            const hasVariables = variables.length > 0;

            if (hasVariables) {
                setSelectedGroup(group);
                setShowVariableDialog(true);
            } else {
                onPromptSelect(promptText);
                onClose();
                setSearchValue("");
            }
        },
        [onPromptSelect, onClose]
    );

    // Handle item selection (reserved command or prompt)
    const handleSelect = useCallback(
        (item: ReservedCommand | PromptGroup) => {
            if ("command" in item && RESERVED_COMMANDS.some(cmd => cmd.command === item.command)) {
                handleReservedCommandSelect(item as ReservedCommand);
            } else {
                handlePromptSelect(item as PromptGroup);
            }
        },
        [handleReservedCommandSelect, handlePromptSelect]
    );

    // Handle variable dialog completion
    const handleVariableSubmit = useCallback(
        (processedPrompt: string) => {
            onPromptSelect(processedPrompt);
            setShowVariableDialog(false);
            setSelectedGroup(null);
            onClose();
            setSearchValue("");
        },
        [onPromptSelect, onClose]
    );

    // Keyboard navigation
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                onClose();
                setSearchValue("");
                textAreaRef.current?.focus();
            } else if (e.key === "ArrowDown") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.min(prev + 1, allItems.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.max(prev - 1, 0));
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                if (allItems[activeIndex]) {
                    handleSelect(allItems[activeIndex]);
                }
            } else if (e.key === "Backspace" && searchValue === "") {
                onClose();
                textAreaRef.current?.focus();
            }
        },
        [allItems, activeIndex, searchValue, handleSelect, onClose, textAreaRef]
    );

    // Auto-focus input when opened
    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    // Reset active index when search changes
    useEffect(() => {
        setActiveIndex(0);
    }, [searchValue]);

    // Scroll active item into view
    useEffect(() => {
        const activeElement = document.getElementById(`prompt-item-${activeIndex}`);
        if (activeElement) {
            activeElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [activeIndex]);

    if (!isOpen) return null;

    return (
        <>
            {/* Backdrop */}
            <div ref={backdropRef} className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />

            <div data-testid="promptCommand" className="fixed top-1/3 left-1/2 z-50 w-full max-w-[672px] -translate-x-1/2 px-4">
                <div ref={popoverRef} className="flex flex-col rounded-lg border border-[var(--border)] bg-[var(--background)] shadow-lg" style={{ maxHeight: "60vh" }}>
                    {/* Search Input */}
                    <div className="flex items-center gap-2 border-b border-[var(--border)] p-3">
                        <Search className="size-4 text-[var(--muted-foreground)]" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={searchValue}
                            onChange={e => setSearchValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Search by shortcut or name..."
                            className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--muted-foreground)]"
                        />
                    </div>

                    {/* Results List */}
                    <div className="min-h-0 flex-1 overflow-y-auto">
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="size-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                            </div>
                        ) : allItems.length === 0 ? (
                            <div className="flex flex-col items-center justify-center gap-4 p-8 text-center">
                                <p className="text-sm text-[var(--muted-foreground)]">{searchValue ? "No prompts found" : "No prompts available."}</p>
                                {!searchValue && (
                                    <button
                                        onClick={handleNavigateToPrompts}
                                        className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-colors hover:bg-[var(--primary)]/90"
                                    >
                                        <Plus className="size-4" />
                                        Create Prompt
                                    </button>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col p-2">
                                {/* Regular Prompts */}
                                {filteredGroups.map((group, index) => {
                                    return (
                                        <button
                                            key={group.id}
                                            id={`prompt-item-${index}`}
                                            onClick={() => handlePromptSelect(group)}
                                            onMouseEnter={() => {
                                                setIsKeyboardMode(false);
                                                setActiveIndex(index);
                                            }}
                                            className={`w-full rounded-md p-3 text-left transition-colors ${index === activeIndex ? "bg-[var(--accent)]" : !isKeyboardMode ? "hover:bg-[var(--accent)]" : ""}`}
                                        >
                                            <div className="flex items-start gap-3">
                                                <NotepadText className="mt-0.5 size-4 flex-shrink-0 text-[var(--muted-foreground)]" />
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        {group.command && <span className="font-mono text-xs text-[var(--primary)]">/{group.command}</span>}
                                                        <span className="text-sm font-medium">{group.name}</span>
                                                        {group.category && <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-xs text-[var(--muted-foreground)]">{group.category}</span>}
                                                    </div>
                                                    {group.description && <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-foreground)]">{group.description}</p>}
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}

                                {/* Reserved Commands - Always visible at bottom */}
                                {availableReservedCommands.length > 0 && (
                                    <>
                                        {filteredGroups.length > 0 && <div className="my-2 border-t border-[var(--border)]" />}
                                        {availableReservedCommands.map((cmd, index) => {
                                            const actualIndex = filteredGroups.length + index;
                                            const Icon = cmd.icon;
                                            return (
                                                <button
                                                    key={`reserved-${cmd.command}`}
                                                    id={`prompt-item-${actualIndex}`}
                                                    onClick={() => handleReservedCommandSelect(cmd)}
                                                    onMouseEnter={() => {
                                                        setIsKeyboardMode(false);
                                                        setActiveIndex(actualIndex);
                                                    }}
                                                    className={`w-full rounded-md p-3 text-left transition-colors ${actualIndex === activeIndex ? "bg-[var(--accent)]" : !isKeyboardMode ? "hover:bg-[var(--accent)]" : ""}`}
                                                >
                                                    <div className="flex items-start gap-3">
                                                        <Icon className="mt-0.5 size-4 flex-shrink-0 text-[var(--primary)]" />
                                                        <div className="min-w-0 flex-1">
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <span className="font-mono text-xs text-[var(--primary)]">/{cmd.command}</span>
                                                                <span className="text-sm font-medium">{cmd.name}</span>
                                                                <span className="rounded bg-[var(--primary)]/10 px-1.5 py-0.5 text-xs text-[var(--primary)]">Reserved</span>
                                                            </div>
                                                            <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-foreground)]">{cmd.description}</p>
                                                        </div>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Variable Dialog */}
            {showVariableDialog && selectedGroup && (
                <VariableDialog
                    group={selectedGroup}
                    onSubmit={handleVariableSubmit}
                    onClose={() => {
                        setShowVariableDialog(false);
                        setSelectedGroup(null);
                        // Don't close the main popover - let user select a different prompt
                    }}
                />
            )}
        </>
    );
};
