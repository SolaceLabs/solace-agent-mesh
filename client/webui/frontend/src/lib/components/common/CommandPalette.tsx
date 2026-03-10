import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent } from "@/lib/components/ui/dialog";
import { Input } from "@/lib/components/ui/input";
import { cn } from "@/lib/utils";
import { Command, Search, MessageSquarePlus } from "lucide-react";
import { ActionRegistry, DynamicNavigationLoader, initializeActions, isExecutableAction, createChatAction } from "./actions";
import type { ExecutableAction } from "./actions";
import { useProjectContext } from "@/lib/providers/ProjectProvider";
import { useThemeContext, useChatContext } from "@/lib/hooks";

function fuzzyMatch(search: string, text: string): number {
    const searchLower = search.toLowerCase();
    const textLower = text.toLowerCase();

    // Exact match gets highest score
    if (textLower === searchLower) return 1000;

    // Starts with search gets high score
    if (textLower.startsWith(searchLower)) return 900;

    // Contains search gets medium score
    if (textLower.includes(searchLower)) return 500;

    // Calculate fuzzy match score
    let score = 0;
    let searchIndex = 0;

    for (let i = 0; i < textLower.length && searchIndex < searchLower.length; i++) {
        if (textLower[i] === searchLower[searchIndex]) {
            score += 1;
            searchIndex++;
        }
    }

    // Return score only if all search characters were matched
    return searchIndex === searchLower.length ? score * 10 : 0;
}

export function CommandPalette() {
    const navigate = useNavigate();
    const { projects } = useProjectContext();
    const { toggleTheme, setTheme } = useThemeContext();
    const { startNewChatWithPrompt } = useChatContext();
    const [isOpen, setIsOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [actions, setActions] = useState<ExecutableAction[]>([]);

    // Initialize actions on mount
    useEffect(() => {
        initializeActions();
        const registry = ActionRegistry.getInstance();
        setActions(registry.getAllActions());
    }, []);

    // Load dynamic actions when dialog opens
    useEffect(() => {
        if (isOpen) {
            const loadDynamicActions = async () => {
                const loader = DynamicNavigationLoader.getInstance();

                // Load project actions if we have projects
                if (projects.length > 0) {
                    await loader.loadProjectActions(projects);
                }

                // Refresh actions list
                const registry = ActionRegistry.getInstance();
                setActions(registry.getAllActions());
            };

            loadDynamicActions();
        }
    }, [isOpen, projects]);

    // Filter and sort actions based on search query
    const filteredActions = useMemo(() => {
        const query = searchQuery.trim();

        if (!query) {
            return actions;
        }

        const scored = actions
            .map(action => {
                const labelScore = fuzzyMatch(query, action.label);
                const descScore = action.description ? fuzzyMatch(query, action.description) * 0.5 : 0;
                const keywordsScore = action.keywords ? action.keywords.reduce((sum, keyword) => sum + fuzzyMatch(query, keyword) * 0.3, 0) : 0;
                return {
                    action,
                    score: labelScore + descScore + keywordsScore,
                };
            })
            .filter(item => item.score > 0)
            .sort((a, b) => b.score - a.score);

        return scored.map(item => item.action);
    }, [searchQuery, actions]);

    // Create fallback "Ask" action when there's a search query
    const askAction = useMemo(() => {
        const query = searchQuery.trim();
        if (!query) return null;

        return createChatAction({
            id: "chat:ask",
            label: `Ask: "${query}"`,
            prompt: query,
            description: "Start a new chat with this question",
            keywords: [],
        });
    }, [searchQuery]);

    // Reset state when dialog opens/closes
    useEffect(() => {
        if (!isOpen) {
            setSearchQuery("");
            setSelectedIndex(0);
        }
    }, [isOpen]);

    const handleActionSelect = useCallback(
        (action: ExecutableAction) => {
            if (isExecutableAction(action)) {
                try {
                    action.execute({
                        navigate,
                        toggleTheme,
                        setTheme,
                        startNewChatWithPrompt,
                    });
                    setIsOpen(false);
                } catch (error) {
                    console.error("Error executing action:", error);
                }
            }
        },
        [navigate, toggleTheme, setTheme, startNewChatWithPrompt]
    );

    // Handle keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Cmd+K (Mac) or Ctrl+K (PC)
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                setIsOpen(prev => !prev);
            }

            // Handle navigation and selection when dialog is open
            if (isOpen) {
                const totalItems = filteredActions.length + (askAction ? 1 : 0);

                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setSelectedIndex(prev => (prev + 1) % totalItems);
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setSelectedIndex(prev => (prev - 1 + totalItems) % totalItems);
                } else if (e.key === "Enter") {
                    e.preventDefault();
                    if (selectedIndex < filteredActions.length && filteredActions.length > 0) {
                        handleActionSelect(filteredActions[selectedIndex]);
                    } else if (askAction && selectedIndex === filteredActions.length) {
                        handleActionSelect(askAction);
                    }
                } else if (e.key === "Escape") {
                    e.preventDefault();
                    setIsOpen(false);
                }
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, filteredActions, askAction, selectedIndex, handleActionSelect]);

    // Update selected index when filtered results change
    useEffect(() => {
        setSelectedIndex(0);
    }, [searchQuery]);

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent className="max-w-2xl p-0" showCloseButton={false}>
                <div className="flex flex-col">
                    {/* Search Input */}
                    <div className="flex items-center border-b px-4 py-3">
                        <Search className="mr-2 size-4 shrink-0 opacity-50" />
                        <Input placeholder="Search for actions..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="border-0 shadow-none focus-visible:border-0 focus-visible:ring-0" autoFocus />
                        <kbd className="bg-muted pointer-events-none ml-auto hidden h-5 items-center gap-1 rounded border px-1.5 font-mono text-[10px] font-medium opacity-100 select-none sm:flex">
                            <Command className="size-3" />K
                        </kbd>
                    </div>

                    {/* Actions List */}
                    <div className="max-h-[400px] overflow-y-auto p-2">
                        {filteredActions.length === 0 && !askAction ? (
                            <div className="text-muted-foreground py-6 text-center text-sm">No actions found</div>
                        ) : (
                            <div className="space-y-1">
                                {filteredActions.map((action, index) => (
                                    <button
                                        key={action.id}
                                        onClick={() => handleActionSelect(action)}
                                        onMouseEnter={() => setSelectedIndex(index)}
                                        className={cn("w-full rounded-xs px-3 py-2 text-left transition-colors", "hover:bg-accent hover:text-accent-foreground", index === selectedIndex && "bg-accent text-accent-foreground")}
                                    >
                                        <div className="font-medium">{action.label}</div>
                                        {action.description && <div className="text-muted-foreground text-xs">{action.description}</div>}
                                    </button>
                                ))}

                                {/* Fallback: Ask as Chat Action */}
                                {askAction && (
                                    <>
                                        {filteredActions.length > 0 && <div className="my-2 border-t" />}
                                        <button
                                            onClick={() => handleActionSelect(askAction)}
                                            onMouseEnter={() => setSelectedIndex(filteredActions.length)}
                                            className={cn(
                                                "w-full rounded-xs px-3 py-2.5 text-left transition-all duration-200",
                                                "border-2 border-dashed shadow-sm",
                                                // Light mode colors
                                                "border-[var(--color-brand-wMain)] bg-[var(--color-brand-w30)]",
                                                // Dark mode colors - semi-transparent overlay
                                                "dark:border-[var(--color-brand-w60)] dark:bg-[rgba(0,200,149,0.15)]",
                                                // Light mode hover
                                                "hover:border-solid hover:bg-[var(--color-brand-w60)] hover:shadow-md",
                                                // Dark mode hover - stronger overlay with teal glow
                                                "dark:hover:bg-[rgba(0,200,149,0.25)] dark:hover:shadow-[0_0_12px_rgba(0,200,149,0.3)]",
                                                // Selected state
                                                filteredActions.length === selectedIndex && "border-solid shadow-md",
                                                filteredActions.length === selectedIndex && "bg-[var(--color-brand-w60)]",
                                                filteredActions.length === selectedIndex && "dark:bg-[rgba(0,200,149,0.25)] dark:shadow-[0_0_12px_rgba(0,200,149,0.3)]"
                                            )}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={cn("flex size-8 shrink-0 items-center justify-center rounded-full", "bg-[var(--color-brand-wMain)]", "dark:bg-[var(--color-brand-w60)]")}>
                                                    <MessageSquarePlus className="size-4 text-white" />
                                                </div>
                                                <div className="flex-1">
                                                    <div className="text-foreground font-semibold">{askAction.label}</div>
                                                    <div className="text-muted-foreground text-xs">{askAction.description}</div>
                                                </div>
                                            </div>
                                        </button>
                                    </>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Footer with keyboard hints */}
                    <div className="text-muted-foreground border-t px-4 py-2 text-xs">
                        <div className="flex items-center justify-between">
                            <span>Navigate with ↑↓ • Select with ↵</span>
                            {askAction ? <span className="font-medium text-[var(--color-brand-wMain)]">Press ↵ to ask in chat</span> : <span>Close with Esc</span>}
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
