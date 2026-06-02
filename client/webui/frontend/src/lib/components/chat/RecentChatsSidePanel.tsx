import React, { useState } from "react";
import { Link } from "react-router-dom";
import { User } from "lucide-react";

import { RecentChatsList } from "./RecentChatsList";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { useChatSurface } from "@/lib/hooks";
import { navButtonStyles, iconWrapperStyles, iconStyles, navTextStyles } from "@/lib/components/navigation/navigationStyles";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";

/**
 * Embedded-only left drawer listing the pinned agent's recent chats, with the same
 * bottom User Account section as the navigation sidebar. Dark-themed to match the
 * navigation surface. Toggled from the chat header (left of New Chat).
 */
export const RecentChatsSidePanel: React.FC = () => {
    const { pinnedAgent } = useChatSurface();
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);

    const viewAllTo = pinnedAgent ? `/agent-mode/recent-chats?agent=${encodeURIComponent(pinnedAgent)}` : "/agent-mode/recent-chats";

    return (
        <div className="flex h-full w-100 flex-col border-r border-(--darkSurface-border) bg-(--darkSurface-bg)">
            <div className="mb-2 flex h-20 items-center justify-between border-b px-6 pt-6 pb-2">
                <span className="text-sm font-bold text-(--darkSurface-textMuted)">Recent Chats</span>
                <Link to={viewAllTo} className="cursor-pointer text-sm font-bold text-(--darkSurface-buttonText) no-underline hover:text-(--darkSurface-buttonTextHover)">
                    View All
                </Link>
            </div>
            <div className="scrollbar-subtle min-h-0 flex-1 overflow-y-auto">
                <RecentChatsList maxItems={MAX_RECENT_CHATS} agentId={pinnedAgent ?? undefined} />
            </div>

            {/* User Account section — mirrors the navigation sidebar's bottom item. */}
            <div className="mt-auto border-t border-(--secondary-w70) py-3">
                <button onClick={() => setIsSettingsOpen(true)} className={navButtonStyles()}>
                    <div className={iconWrapperStyles({ active: false, withMargin: true })}>
                        <User className={iconStyles({ active: false })} />
                    </div>
                    <span className={navTextStyles()}>User Account</span>
                </button>
            </div>

            <SettingsDialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />
        </div>
    );
};
