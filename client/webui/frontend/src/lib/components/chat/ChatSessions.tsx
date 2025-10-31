import { SessionList } from "./SessionList";
import { useConfigContext, useChatContext } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";

export const ChatSessions = () => {
    const { persistenceEnabled } = useConfigContext();
    const { sessionName } = useChatContext();
    const { projects } = useProjectContext();

    if (persistenceEnabled) return <SessionList projects={projects} />;

    // When persistence is disabled, show simple single-session view like in main
    return (
        <div className="flex h-full flex-col">
            <div className="flex-1 overflow-y-auto px-4">
                {/* Current Session */}
                <div className="bg-accent/50 hover:bg-accent mb-3 cursor-pointer rounded-md p-3">
                    <div className="text-foreground truncate text-sm font-medium text-nowrap">{sessionName || "New Chat"}</div>
                    <div className="text-muted-foreground mt-1 text-xs">Current session</div>
                </div>

                {/* Multi-session notice */}
                <div className="text-muted-foreground mt-4 text-center text-xs">Persistence is not enabled.</div>
            </div>
        </div>
    );
};
