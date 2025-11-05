/**
 * Displays a popover with searchable prompt library when "/" is typed
 * Also handles reserved commands like /create-template
 */

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Search, FileText } from 'lucide-react';
import type { PromptGroup } from '@/lib/types/prompts';
import type { MessageFE } from '@/lib/types';
import { detectVariables } from '@/lib/utils/promptUtils';
import { VariableDialog } from './VariableDialog';

interface ReservedCommand {
    command: string;
    name: string;
    description: string;
    icon: typeof FileText;
}

const RESERVED_COMMANDS: ReservedCommand[] = [
    {
        command: 'create-template',
        name: 'Create Template from Session',
        description: 'Create a reusable prompt template from this conversation',
        icon: FileText,
    },
];

interface PromptsCommandProps {
    isOpen: boolean;
    onClose: () => void;
    textAreaRef: React.RefObject<HTMLTextAreaElement | null>;
    onPromptSelect: (promptText: string) => void;
    messages?: MessageFE[];
    onReservedCommand?: (command: string, context?: string) => void;
}

export const PromptsCommand: React.FC<PromptsCommandProps> = ({
    isOpen,
    onClose,
    textAreaRef,
    onPromptSelect,
    messages = [],
    onReservedCommand,
}) => {
    const [searchValue, setSearchValue] = useState('');
    const [activeIndex, setActiveIndex] = useState(0);
    const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedGroup, setSelectedGroup] = useState<PromptGroup | null>(null);
    const [showVariableDialog, setShowVariableDialog] = useState(false);
    
    const inputRef = useRef<HTMLInputElement>(null);
    const popoverRef = useRef<HTMLDivElement>(null);

    // Fetch prompt groups when opened
    useEffect(() => {
        if (!isOpen) return;
        
        const fetchPromptGroups = async () => {
            setIsLoading(true);
            try {
                const response = await fetch('/api/v1/prompts/groups/all', {
                    credentials: 'include',
                });
                if (response.ok) {
                    const data = await response.json();
                    setPromptGroups(data);
                }
            } catch (error) {
                console.error('Failed to fetch prompt groups:', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPromptGroups();
    }, [isOpen]);

    // Filter reserved commands based on search and availability
    const filteredReservedCommands = useMemo(() => {
        // Only show create-template if there are user messages in the session
        const hasUserMessages = messages.some(m => m.isUser && !m.isStatusBubble);
        const availableCommands = RESERVED_COMMANDS.filter(cmd => {
            if (cmd.command === 'create-template') {
                return hasUserMessages;
            }
            return true;
        });
        
        if (!searchValue) return availableCommands;
        
        const search = searchValue.toLowerCase();
        return availableCommands.filter(cmd =>
            cmd.command.toLowerCase().includes(search) ||
            cmd.name.toLowerCase().includes(search) ||
            cmd.description.toLowerCase().includes(search)
        );
    }, [searchValue, messages]);

    // Filter prompt groups based on search
    const filteredGroups = useMemo(() => {
        if (!searchValue) return promptGroups;
        
        const search = searchValue.toLowerCase();
        return promptGroups.filter(group => 
            group.name.toLowerCase().includes(search) ||
            group.description?.toLowerCase().includes(search) ||
            group.command?.toLowerCase().includes(search) ||
            group.category?.toLowerCase().includes(search)
        );
    }, [promptGroups, searchValue]);

    // Combine reserved commands and prompts for display
    const allItems = useMemo(() => {
        return [...filteredReservedCommands, ...filteredGroups];
    }, [filteredReservedCommands, filteredGroups]);

    // Format session history for context
    const formatSessionHistory = useCallback((messages: MessageFE[]): string => {
        return messages
            .filter(m => !m.isStatusBubble && !m.isError && !m.authenticationLink)
            .map(m => {
                const role = m.isUser ? 'User' : 'Assistant';
                const text = m.parts
                    ?.filter(p => p.kind === 'text')
                    .map(p => (p as any).text)
                    .join('\n') || '';
                return `${role}: ${text}`;
            })
            .join('\n\n');
    }, []);

    // Handle reserved command selection
    const handleReservedCommandSelect = useCallback((cmd: ReservedCommand) => {
        if (cmd.command === 'create-template' && onReservedCommand) {
            const sessionHistory = formatSessionHistory(messages);
            onReservedCommand(cmd.command, sessionHistory);
            onClose();
            setSearchValue('');
        }
    }, [messages, formatSessionHistory, onReservedCommand, onClose]);

    // Handle prompt selection
    const handlePromptSelect = useCallback((group: PromptGroup) => {
        const promptText = group.production_prompt?.prompt_text || '';
        
        // Check for variables
        const variables = detectVariables(promptText);
        const hasVariables = variables.length > 0;
        
        if (hasVariables) {
            setSelectedGroup(group);
            setShowVariableDialog(true);
        } else {
            onPromptSelect(promptText);
            onClose();
            setSearchValue('');
        }
    }, [onPromptSelect, onClose]);

    // Handle item selection (reserved command or prompt)
    const handleSelect = useCallback((item: ReservedCommand | PromptGroup) => {
        if ('command' in item && RESERVED_COMMANDS.some(cmd => cmd.command === item.command)) {
            handleReservedCommandSelect(item as ReservedCommand);
        } else {
            handlePromptSelect(item as PromptGroup);
        }
    }, [handleReservedCommandSelect, handlePromptSelect]);

    // Handle variable dialog completion
    const handleVariableSubmit = useCallback((processedPrompt: string) => {
        onPromptSelect(processedPrompt);
        setShowVariableDialog(false);
        setSelectedGroup(null);
        onClose();
        setSearchValue('');
    }, [onPromptSelect, onClose]);

    // Keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            onClose();
            setSearchValue('');
            textAreaRef.current?.focus();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveIndex(prev => Math.min(prev + 1, allItems.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveIndex(prev => Math.max(prev - 1, 0));
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            if (allItems[activeIndex]) {
                handleSelect(allItems[activeIndex]);
            }
        } else if (e.key === 'Backspace' && searchValue === '') {
            onClose();
            textAreaRef.current?.focus();
        }
    }, [allItems, activeIndex, searchValue, handleSelect, onClose, textAreaRef]);

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
            activeElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, [activeIndex]);

    if (!isOpen) return null;

    return (
        <>
            <div className="absolute bottom-14 left-0 right-0 z-50 mx-auto max-w-2xl px-4">
                <div 
                    ref={popoverRef}
                    className="rounded-lg border border-[var(--border)] bg-[var(--background)] shadow-lg"
                >
                    {/* Search Input */}
                    <div className="flex items-center gap-2 border-b border-[var(--border)] p-3">
                        <Search className="size-4 text-[var(--muted-foreground)]" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={searchValue}
                            onChange={(e) => setSearchValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Search prompts... (use / command or name)"
                            className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--muted-foreground)]"
                        />
                        <kbd className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-xs text-[var(--muted-foreground)]">
                            ESC
                        </kbd>
                    </div>

                    {/* Results List */}
                    <div className="max-h-80 overflow-y-auto">
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="size-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                            </div>
                        ) : allItems.length === 0 ? (
                            <div className="p-8 text-center text-sm text-[var(--muted-foreground)]">
                                {searchValue ? 'No prompts found' : 'No prompts available. Create one in the Prompts panel.'}
                            </div>
                        ) : (
                            <div className="p-2">
                                {/* Reserved Commands */}
                                {filteredReservedCommands.length > 0 && (
                                    <>
                                        {filteredReservedCommands.map((cmd, index) => {
                                            const Icon = cmd.icon;
                                            return (
                                                <button
                                                    key={`reserved-${cmd.command}`}
                                                    id={`prompt-item-${index}`}
                                                    onClick={() => handleReservedCommandSelect(cmd)}
                                                    className={`w-full rounded-md p-3 text-left transition-colors ${
                                                        index === activeIndex
                                                            ? 'bg-[var(--accent)]'
                                                            : 'hover:bg-[var(--accent)]'
                                                    }`}
                                                >
                                                    <div className="flex items-start gap-3">
                                                        <Icon className="mt-0.5 size-4 flex-shrink-0 text-[var(--primary)]" />
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-center gap-2 flex-wrap">
                                                                <span className="font-mono text-xs text-[var(--primary)]">
                                                                    /{cmd.command}
                                                                </span>
                                                                <span className="font-medium text-sm">
                                                                    {cmd.name}
                                                                </span>
                                                                <span className="rounded bg-[var(--primary)]/10 px-1.5 py-0.5 text-xs text-[var(--primary)]">
                                                                    Reserved
                                                                </span>
                                                            </div>
                                                            <p className="mt-1 text-xs text-[var(--muted-foreground)] line-clamp-2">
                                                                {cmd.description}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                        {filteredGroups.length > 0 && (
                                            <div className="my-2 border-t border-[var(--border)]" />
                                        )}
                                    </>
                                )}

                                {/* Regular Prompts */}
                                {filteredGroups.map((group, index) => {
                                    const actualIndex = filteredReservedCommands.length + index;
                                    return (
                                        <button
                                            key={group.id}
                                            id={`prompt-item-${actualIndex}`}
                                            onClick={() => handlePromptSelect(group)}
                                            className={`w-full rounded-md p-3 text-left transition-colors ${
                                                actualIndex === activeIndex
                                                    ? 'bg-[var(--accent)]'
                                                    : 'hover:bg-[var(--accent)]'
                                            }`}
                                        >
                                            <div className="flex items-start gap-3">
                                                <FileText className="mt-0.5 size-4 flex-shrink-0 text-[var(--muted-foreground)]" />
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        {group.command && (
                                                            <span className="font-mono text-xs text-[var(--primary)]">
                                                                /{group.command}
                                                            </span>
                                                        )}
                                                        <span className="font-medium text-sm">
                                                            {group.name}
                                                        </span>
                                                        {group.category && (
                                                            <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-xs text-[var(--muted-foreground)]">
                                                                {group.category}
                                                            </span>
                                                        )}
                                                    </div>
                                                    {group.description && (
                                                        <p className="mt-1 text-xs text-[var(--muted-foreground)] line-clamp-2">
                                                            {group.description}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
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
                        onClose();
                    }}
                />
            )}
        </>
    );
};