import React from "react";

import { PanelLeftIcon } from "lucide-react";

import { Button } from "@/lib/components/ui";

import { ChatSessions } from "./ChatSessions";
import { ChatSessionDialog } from "./ChatSessionDialog";

interface SessionSidePanelProps {
    onToggle: () => void;
}

export const SessionSidePanel: React.FC<SessionSidePanelProps> = ({ onToggle }) => {
    return (
        <div className={`bg-background flex h-full w-100 flex-col border-r`}>
            <div className="flex items-center justify-between px-4 pt-[35px] pb-3">
                <Button variant="ghost" onClick={onToggle} className="p-2" data-testid="hideChatSessions" tooltip="Hide Chat Sessions">
                    <PanelLeftIcon className="size-5" />
                </Button>

                <ChatSessionDialog buttonText="New Chat" />
            </div>

            {/* Chat Sessions */}
            <div className="mt-1 min-h-0 flex-1">
                <ChatSessions />
            </div>
        </div>
    );
};
