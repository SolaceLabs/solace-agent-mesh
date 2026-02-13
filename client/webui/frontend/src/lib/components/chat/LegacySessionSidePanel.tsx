import React from "react";

import { PanelLeftIcon } from "lucide-react";

import { Button } from "@/lib/components/ui";

import { LegacyChatSessions } from "./LegacyChatSessions";
import { ChatSessionDialog } from "./ChatSessionDialog";

interface LegacySessionSidePanelProps {
    onToggle: () => void;
}

/**
 * Legacy Session Side Panel - Simple chat sessions list from main branch
 * Used when newNavigation feature flag is false
 */
export const LegacySessionSidePanel: React.FC<LegacySessionSidePanelProps> = ({ onToggle }) => {
    return (
        <div className="bg-background flex h-full w-100 flex-col border-r">
            <div className="flex h-20 justify-between border-b px-2 pt-[35px]">
                <div className="flex items-center gap-2">
                    <Button variant="ghost" onClick={onToggle} data-testid="hideChatSessions" tooltip="Hide Chat Sessions">
                        <PanelLeftIcon className="size-5" />
                    </Button>
                    <div className="text-xl">Chats</div>
                </div>

                <div className="flex items-center">
                    <ChatSessionDialog buttonText="New Chat" />
                </div>
            </div>

            {/* Chat Sessions */}
            <div className="mt-1 min-h-0 flex-1">
                <LegacyChatSessions />
            </div>
        </div>
    );
};
