import React, { useEffect, useRef, useState } from "react";
import { MessageSquarePlus, Copy, FileText, Lightbulb, Send } from "lucide-react";

import { Button, ChatInput } from "@/lib/components/ui";
import type { SelectionContextMenuProps } from "./types";

export const SelectionContextMenu: React.FC<SelectionContextMenuProps> = ({
    isOpen,
    position,
    selectedText,
    onClose,
}) => {
    const menuRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const [showCustomInput, setShowCustomInput] = useState(false);
    const [customQuery, setCustomQuery] = useState("");
    const savedSelectionRef = useRef<Range | null>(null);
    const hasRestoredSelectionRef = useRef(false);

    // Save the current selection when menu opens
    useEffect(() => {
        if (isOpen && !savedSelectionRef.current) {
            const selection = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                savedSelectionRef.current = selection.getRangeAt(0).cloneRange();
            }
        }
    }, [isOpen]);

    // Restore selection when showing custom input
    useEffect(() => {
        if (showCustomInput && savedSelectionRef.current) {
            // Small delay to ensure DOM is ready
            setTimeout(() => {
                const selection = window.getSelection();
                if (selection) {
                    selection.removeAllRanges();
                    selection.addRange(savedSelectionRef.current!);
                }
            }, 0);
        }
    }, [showCustomInput]);

    // Handle click outside to close menu
    useEffect(() => {
        if (!isOpen) return;

        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                onClose();
                setShowCustomInput(false);
                setCustomQuery("");
                savedSelectionRef.current = null;
            }
        };

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                if (showCustomInput) {
                    setShowCustomInput(false);
                    setCustomQuery("");
                } else {
                    onClose();
                    savedSelectionRef.current = null;
                }
            }
        };

        const handleScroll = () => {
            onClose();
            setShowCustomInput(false);
            setCustomQuery("");
            savedSelectionRef.current = null;
        };

        // Add listeners with a small delay to avoid immediate closure
        setTimeout(() => {
            document.addEventListener("mousedown", handleClickOutside);
            document.addEventListener("keydown", handleEscape);
            window.addEventListener("scroll", handleScroll, true);
        }, 100);

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("keydown", handleEscape);
            window.removeEventListener("scroll", handleScroll, true);
        };
    }, [isOpen, onClose, showCustomInput]);

    // Focus input when custom input is shown
    useEffect(() => {
        if (showCustomInput && inputRef.current) {
            inputRef.current.focus();
        }
    }, [showCustomInput]);

    const handleCopyToClipboard = async () => {
        try {
            await navigator.clipboard.writeText(selectedText);
            onClose();
            savedSelectionRef.current = null;
        } catch (error) {
            console.error("Failed to copy text:", error);
        }
    };

    const handleQuickAction = (action: string) => {
        let prompt = "";
        let autoSubmit = false;
        
        switch (action) {
            case "summarize":
                prompt = "Summarize this:";
                autoSubmit = true;
                break;
            case "explain":
                prompt = "Explain this in detail:";
                autoSubmit = true;
                break;
            case "custom":
                setShowCustomInput(true);
                hasRestoredSelectionRef.current = false; // Reset flag when showing custom input
                return;
        }
        
        // Dispatch event with the prompt and autoSubmit flag
        window.dispatchEvent(
            new CustomEvent("follow-up-question", {
                detail: {
                    text: selectedText,
                    prompt: prompt,
                    autoSubmit: autoSubmit
                },
            })
        );
        onClose();
        setShowCustomInput(false);
        setCustomQuery("");
        savedSelectionRef.current = null;
    };

    const handleCustomSubmit = () => {
        if (customQuery.trim()) {
            window.dispatchEvent(
                new CustomEvent("follow-up-question", {
                    detail: {
                        text: selectedText,
                        prompt: customQuery.trim(),
                        autoSubmit: true  // Also auto-submit custom questions
                    },
                })
            );
            onClose();
            setShowCustomInput(false);
            setCustomQuery("");
            savedSelectionRef.current = null;
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleCustomSubmit();
        }
    };

    if (!isOpen || !position) {
        return null;
    }

    return (
        <div
            ref={menuRef}
            className="fixed z-50 animate-in fade-in-0 zoom-in-95 duration-200"
            style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
                transform: "translate(-50%, 0)",
            }}
        >
            <div className={`bg-background rounded-md border shadow-lg p-1 w-auto ${!showCustomInput ? 'max-w-[160px]' : ''}`}>
                {!showCustomInput ? (
                    <>
                        <Button
                            variant="ghost"
                            className="w-full justify-start gap-1.5 text-xs font-normal px-2 py-1.5 h-auto"
                            onClick={() => handleQuickAction("summarize")}
                        >
                            <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="truncate">Summarize</span>
                        </Button>
                        <Button
                            variant="ghost"
                            className="w-full justify-start gap-1.5 text-xs font-normal px-2 py-1.5 h-auto"
                            onClick={() => handleQuickAction("explain")}
                        >
                            <Lightbulb className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="truncate">Explain</span>
                        </Button>
                        <Button
                            variant="ghost"
                            className="w-full justify-start gap-1.5 text-xs font-normal px-2 py-1.5 h-auto"
                            onClick={() => handleQuickAction("custom")}
                        >
                            <MessageSquarePlus className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="truncate">Custom...</span>
                        </Button>
                        <div className="my-0.5 border-t" />
                        <Button
                            variant="ghost"
                            className="w-full justify-start gap-1.5 text-xs font-normal px-2 py-1.5 h-auto"
                            onClick={handleCopyToClipboard}
                        >
                            <Copy className="h-3.5 w-3.5 flex-shrink-0" />
                            <span className="truncate">Copy</span>
                        </Button>
                    </>
                ) : (
                    <div className="p-2 min-w-[320px] bg-background">
                        <div className="mb-2 text-xs text-muted-foreground">
                            Ask about the selected text:
                        </div>
                        <div className="mb-2 p-2 bg-muted/50 rounded text-xs italic border border-border max-h-[60px] overflow-y-auto">
                            "{selectedText.length > 150 ? selectedText.substring(0, 150) + '...' : selectedText}"
                        </div>
                        <div className="relative">
                            <ChatInput
                                ref={inputRef}
                                value={customQuery}
                                onChange={(e) => setCustomQuery(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Type your question..."
                                className="min-h-[60px] text-sm pr-10 bg-background"
                                rows={2}
                            />
                            <Button
                                size="icon"
                                variant="ghost"
                                onClick={handleCustomSubmit}
                                disabled={!customQuery.trim()}
                                className="absolute right-2 bottom-2 h-7 w-7"
                            >
                                <Send className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};