import { CalendarClock, FolderOpen, Hammer, MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Session } from "@/lib/types";

interface SessionIconProps {
    session: Session;
    className?: string;
}

/**
 * Renders the appropriate icon for a chat session based on its type:
 * - Builder sessions (agentId === "Builder") → Hammer
 * - Project chats (has projectId) → FolderOpen
 * - Scheduled tasks (source === "scheduler") → CalendarClock
 * - Regular chats → MessageCircle
 */
export function SessionIcon({ session, className }: SessionIconProps) {
    const iconClass = cn("h-3.5 w-3.5 shrink-0", className);

    if (session.agentId === "Builder") {
        return <Hammer className={iconClass} />;
    }
    if (session.projectId) {
        return <FolderOpen className={iconClass} />;
    }
    if (session.source === "scheduler") {
        return <CalendarClock className={iconClass} />;
    }
    return <MessageCircle className={iconClass} />;
}
