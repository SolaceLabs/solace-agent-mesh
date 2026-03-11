import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { cva } from "class-variance-authority";
import { UserSearch } from "lucide-react";

import { listSharedWithMe } from "@/lib/api/shareApi";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { SharedWithMeItem } from "@/lib/types/share";

const sharedChatButtonStyles = cva(["flex", "h-10", "w-full", "cursor-pointer", "items-center", "gap-2", "pr-4", "pl-6", "text-left", "transition-colors", "hover:bg-(--color-background-w100)"], {
    variants: {
        active: {
            true: "bg-(--color-background-w100)",
            false: "",
        },
    },
    defaultVariants: { active: false },
});

const sharedChatTextStyles = cva(["block", "truncate", "text-sm"], {
    variants: {
        active: {
            true: "text-(--color-primary-text-w10)",
            false: "text-(--color-secondary-text-w50)",
        },
    },
    defaultVariants: { active: false },
});

interface SharedChatsListProps {
    maxItems?: number;
}

export function SharedChatsList({ maxItems = 5 }: SharedChatsListProps) {
    const navigate = useNavigate();
    const [sharedChats, setSharedChats] = useState<SharedWithMeItem[]>([]);

    const fetchSharedChats = useCallback(async () => {
        try {
            const items = await listSharedWithMe();
            setSharedChats(items.slice(0, maxItems));
        } catch (error) {
            console.error("Failed to fetch shared chats:", error);
        }
    }, [maxItems]);

    useEffect(() => {
        fetchSharedChats();
    }, [fetchSharedChats]);

    if (sharedChats.length === 0) {
        return null;
    }

    return (
        <>
            <div className="my-4 border-t border-[var(--color-secondary-w70)]" />
            <div className="mb-2 flex items-center justify-between pr-4 pl-6">
                <span className="text-sm font-bold text-[var(--color-secondary-text-wMain)]">Shared with me</span>
            </div>
            <div>
                {sharedChats.map(item => (
                    <Tooltip key={item.share_id}>
                        <TooltipTrigger asChild>
                            <button onClick={() => navigate(`/shared-chat/${item.share_id}`)} className={sharedChatButtonStyles({ active: false })}>
                                <UserSearch className="h-4 w-4 flex-shrink-0 text-[var(--color-secondary-text-w50)]" />
                                <span className={sharedChatTextStyles({ active: false })}>{item.title}</span>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side="right">
                            <div className="text-xs">
                                <div className="font-semibold">{item.title}</div>
                                <div className="text-muted-foreground">from {item.owner_email}</div>
                            </div>
                        </TooltipContent>
                    </Tooltip>
                ))}
            </div>
        </>
    );
}
