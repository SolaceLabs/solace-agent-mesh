import { useState, useEffect } from "react";
import { X, Save, Trash2 } from "lucide-react";
import { Badge } from "@/lib/components/ui/badge";
import { Button } from "@/lib/components/ui/button";
import { Input } from "@/lib/components/ui/input";
import { getDevUserId, setDevUserId, clearDevUserId } from "@/lib/utils/devMode";

export const DevUserIdControl: React.FC = () => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [userId, setUserId] = useState("");
    const [isActive, setIsActive] = useState(false);

    // Load initial state from localStorage
    useEffect(() => {
        const storedUserId = getDevUserId();
        if (storedUserId) {
            setUserId(storedUserId);
            setIsActive(true);
        }
    }, []);

    const handleSave = () => {
        if (userId.trim()) {
            setDevUserId(userId.trim());
            setIsActive(true);
            setIsExpanded(false);
        }
    };

    const handleClear = () => {
        clearDevUserId();
        setUserId("");
        setIsActive(false);
        setIsExpanded(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            handleSave();
        } else if (e.key === "Escape") {
            setIsExpanded(false);
        }
    };

    if (!isExpanded) {
        return (
            <Badge
                variant={isActive ? "default" : "outline"}
                type={isActive ? "info" : undefined}
                className="cursor-pointer transition-all hover:opacity-80"
                onClick={() => setIsExpanded(true)}
                aria-label={isActive ? `Dev Mode Active: ${userId}` : "Dev Mode Inactive"}
            >
                {isActive ? `Dev: ${userId}` : "Dev Mode"}
            </Badge>
        );
    }

    return (
        <div className="flex items-center gap-2 rounded-md border bg-background p-2 shadow-sm">
            <Input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter user_id"
                className="h-8 w-40"
                autoFocus
                aria-label="Development User ID"
            />
            <Button
                variant="ghost"
                size="sm"
                onClick={handleSave}
                disabled={!userId.trim()}
                className="h-8 w-8 p-0"
                tooltip="Save User ID"
                aria-label="Save User ID"
            >
                <Save className="size-4" />
            </Button>
            {isActive && (
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClear}
                    className="h-8 w-8 p-0"
                    tooltip="Clear User ID"
                    aria-label="Clear User ID"
                >
                    <Trash2 className="size-4" />
                </Button>
            )}
            <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(false)}
                className="h-8 w-8 p-0"
                tooltip="Close"
                aria-label="Close"
            >
                <X className="size-4" />
            </Button>
        </div>
    );
};