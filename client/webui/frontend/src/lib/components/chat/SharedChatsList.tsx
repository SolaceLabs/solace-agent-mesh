import { useEffect, useState, useCallback, useRef, type MouseEvent } from "react";

import { useNavigate } from "react-router-dom";
import { cva } from "class-variance-authority";
import { Share2 } from "lucide-react";

import { listSharedWithMe } from "@/lib/api/share";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { SharedWithMeItem } from "@/lib/types/share";

const sharedChatButtonStyles = cva(["flex", "h-10", "w-full", "cursor-pointer", "items-center", "gap-2", "pr-4", "pl-6", "text-left", "transition-colors", "hover:bg-(--darkSurface-bgHover)"], {
    variants: {
        active: {
            true: "bg-(--darkSurface-bgActive)",
            false: "",
        },
    },
    defaultVariants: { active: false },
});

const sharedChatTextStyles = cva(["block", "truncate", "text-sm"], {
    variants: {
        active: {
            true: "text-(--darkSurface-text) font-bold",
            false: "text-(--darkSurface-textMuted)",
        },
    },
    defaultVariants: { active: false },
});

interface SharedChatsListProps {
    maxItems?: number;
}

interface SharedChatItemProps {
    item: SharedWithMeItem;
    onClick: (e: MouseEvent) => void;
}

function SharedChatItem({ item, onClick }: SharedChatItemProps) {
    const textRef = useRef<HTMLSpanElement>(null);
    const [isTruncated, setIsTruncated] = useState(false);

    useEffect(() => {
        const element = textRef.current;
        if (element) {
            setIsTruncated(element.scrollWidth > element.clientWidth);
        }
    }, [item.title]);

    const button = (
        <button onClick={onClick} className={sharedChatButtonStyles({ active: false })}>
            <span ref={textRef} className={sharedChatTextStyles({ active: false })}>
                {item.title}
            </span>
        </button>
    );

    if (!isTruncated) {
        return button;
    }

    return (
        <Tooltip>
            <TooltipTrigger asChild>{button}</TooltipTrigger>
            <TooltipContent side="right">
                <p>{item.title}</p>
            </TooltipContent>
        </Tooltip>
    );
}

export function SharedChatsList({ maxItems = 5 }: SharedChatsListProps) {
    const navigate = useNavigate();
    const { handleSwitchSession } = useChatContext();
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
            <div className="my-4 border-t border-(--darkSurface-border)" />
            <div className="mb-2 flex items-center gap-2 pr-4 pl-6">
                <Share2 className="h-4 w-4 text-(--darkSurface-textMuted)" />
                <Tooltip>
                    <TooltipTrigger asChild>
                        <span className="cursor-default text-sm font-bold text-(--darkSurface-textMuted)">Shared with Me</span>
                    </TooltipTrigger>
                    <TooltipContent side="right">Experimental Feature</TooltipContent>
                </Tooltip>
            </div>
            <div>
                {sharedChats.map(item => {
                    const isEditor = item.accessLevel === "RESOURCE_EDITOR" && item.sessionId;
                    const handleClick = (e: MouseEvent) => {
                        e.stopPropagation();
                        if (isEditor && item.sessionId) {
                            handleSwitchSession(item.sessionId);
                            navigate("/chat");
                        } else {
                            navigate(`/shared-chat/${item.shareId}`);
                        }
                    };

                    return <SharedChatItem key={item.shareId} item={item} onClick={handleClick} />;
                })}
            </div>
        </>
    );
}
