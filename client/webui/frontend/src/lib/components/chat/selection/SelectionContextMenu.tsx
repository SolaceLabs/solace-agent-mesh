import React, { useEffect, useRef } from "react";
import { MessageSquarePlus } from "lucide-react";

import { Button } from "@/lib/components/ui";
import type { SelectionContextMenuProps } from "./types";

export const SelectionContextMenu: React.FC<SelectionContextMenuProps> = ({ isOpen, position, selectedText, onClose }) => {
    const menuRef = useRef<HTMLDivElement>(null);

    // Handle click outside to close menu
    useEffect(() => {
        if (!isOpen) return;

        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                onClose();
            }
        };

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                onClose();
            }
        };

        const handleScroll = () => {
            onClose();
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
    }, [isOpen, onClose]);

    const handleAskFollowup = () => {
        // Dispatch event to populate the main chat input with the selected text
        window.dispatchEvent(
            new CustomEvent("follow-up-question", {
                detail: {
                    text: selectedText,
                    prompt: "", // Empty prompt so it just populates with the text
                    autoSubmit: false, // Don't auto-submit, let user type their question
                },
            })
        );
        onClose();
    };

    if (!isOpen || !position) {
        return null;
    }

    return (
        <div
            ref={menuRef}
            className="animate-in fade-in-0 zoom-in-95 fixed z-50 duration-200"
            style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
            }}
        >
            <div className="bg-background w-auto max-w-[160px] rounded-md border p-1 shadow-lg">
                <Button variant="ghost" className="h-auto w-full justify-start gap-1.5 px-2 py-1.5 text-xs font-normal" onClick={handleAskFollowup}>
                    <MessageSquarePlus className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate">Ask Followup</span>
                </Button>
            </div>
        </div>
    );
};
