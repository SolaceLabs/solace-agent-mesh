import React from "react";

import { Menu, Edit } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";

import { ChatSessions } from "./ChatSessions";

interface SessionSidePanelProps {
    onToggle: () => void;
}

export const SessionSidePanel: React.FC<SessionSidePanelProps> = ({ onToggle }) => {
    const { handleNewSession } = useChatContext();

    const handleNewSessionClick = () => {
        handleNewSession();
    };

    return (
        <div className={`bg-background flex h-full w-100 flex-col border-r`}>
            <div className="flex items-center justify-between px-4 pt-[35px] pb-3">
                <Button variant="ghost" onClick={onToggle} className="p-2" tooltip="Collapse Sessions Panel">
                    <Menu className="h-5 w-5" />
                </Button>
                <Button variant="ghost" onClick={handleNewSessionClick} className="justify-start" title="Start New Chat Session">
                    <Edit className="mr-2 h-4 w-4" />
                    New chat
                </Button>
            </div>

            {/* Chat Sessions */}
            <div className="mt-1 min-h-0 flex-1">
                <ChatSessions />
            </div>
        </div>
    );
};
