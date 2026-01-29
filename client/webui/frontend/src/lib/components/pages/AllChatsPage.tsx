import React from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { SessionList } from "@/lib/components/chat/SessionList";
import { Button } from "@/lib/components/ui";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";

export const AllChatsPage: React.FC = () => {
    const navigate = useNavigate();
    const { projects } = useProjectContext();
    const { handleNewSession } = useChatContext();

    const handleNewChatClick = () => {
        navigate("/chat");
        handleNewSession();
    };

    return (
        <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b px-6 py-4">
                <div>
                    <h1 className="text-foreground text-xl font-semibold">All Chats</h1>
                    <p className="text-muted-foreground mt-1 text-sm">View all your chat sessions, search, and filter by project.</p>
                </div>
                <Button onClick={handleNewChatClick} size="sm">
                    <Plus className="mr-2 h-4 w-4" />
                    New Chat
                </Button>
            </div>
            <div className="flex-1 overflow-hidden">
                <SessionList projects={projects} />
            </div>
        </div>
    );
};
