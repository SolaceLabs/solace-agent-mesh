import { SessionList } from "./SessionList";
import { useConfigContext, useChatContext } from "@/lib/hooks";

export const ChatSessions = () => {
    const { persistenceEnabled } = useConfigContext();
    const { sessionName } = useChatContext();

    // When persistence is disabled, show simple single-session view like in main
    if (persistenceEnabled === false) {
        return (
            <div className="flex h-full flex-col">
                <div className="flex-1 overflow-y-auto px-4">
                    {/* Current Session */}
                    <div className="bg-accent/50 hover:bg-accent mb-3 cursor-pointer rounded-md p-3">
                        <div className="text-foreground truncate text-sm font-medium text-nowrap">{sessionName || "New Chat"}</div>
                        <div className="text-muted-foreground mt-1 text-xs">Current session</div>
                    </div>

                    {/* Multi-session notice */}
                    <div className="text-muted-foreground mt-4 text-center text-xs">Multi-session support coming soon</div>
                </div>
            </div>
        );
    }

    // When persistence is enabled, show full session list
    return <SessionList />;
};
