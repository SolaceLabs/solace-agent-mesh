import React, { useState } from "react";

import { PanelLeftIcon, Edit } from "lucide-react";

import { Button } from "@/lib/components/ui";

import { ChatSessions } from "./ChatSessions";
import { ChatSessionDialog } from "./ChatSessionDialog";

interface SessionSidePanelProps {
    onToggle: () => void;
}

export const SessionSidePanel: React.FC<SessionSidePanelProps> = ({ onToggle }) => {
    const [chatSessionDialogOpen, setChatSessionDialogOpen] = useState(false);

    return (
        <div className={`bg-background flex h-full w-100 flex-col border-r`}>
            <div className="flex items-center justify-between px-4 pt-[35px] pb-3">
                <Button variant="ghost" onClick={onToggle} className="p-2" tooltip="Collapse Sessions Panel">
                    <PanelLeftIcon className="size-5" />
                </Button>
                <Button variant="ghost" onClick={() => setChatSessionDialogOpen(true)} tooltip="Start New Chat Session">
                    <Edit className="size-5" />
                    New chat
                </Button>
            </div>

            {/* Chat Sessions */}
            <div className="mt-1 min-h-0 flex-1">
                <ChatSessions />
            </div>

            <ChatSessionDialog isOpen={chatSessionDialogOpen} onClose={() => setChatSessionDialogOpen(false)} />
        </div>
    );
};
