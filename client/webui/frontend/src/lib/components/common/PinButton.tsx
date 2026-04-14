import React from "react";
import { Star } from "lucide-react";
import { Button } from "@/lib/components/ui";

interface PinButtonProps {
    isPinned: boolean;
    onClick: (e: React.MouseEvent) => void;
    disabled?: boolean;
}

/**
 * Shared star/pin button used across card components (Projects, Prompts).
 * Renders a filled star when pinned, outline when not.
 */
export const PinButton: React.FC<PinButtonProps> = ({ isPinned, onClick, disabled }) => {
    return (
        <Button variant="ghost" size="icon" disabled={disabled} onClick={onClick} className={isPinned ? "text-(--primary-wMain)" : "text-(--secondary-text-wMain)"} tooltip={isPinned ? "Remove from favorites" : "Add to favorites"}>
            <Star size={16} fill={isPinned ? "currentColor" : "none"} />
        </Button>
    );
};
