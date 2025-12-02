import { SessionList } from "./SessionList";
import { RecentChatsList } from "./RecentChatsList";
import { useConfigContext, useChatContext } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";

interface ChatSessionsProps {
    /** Maximum number of items to show (for compact view). If not provided, shows all. */
    maxItems?: number;
    /** Callback when "Show All" is clicked */
    onShowAll?: () => void;
    /** Whether to show in compact mode (uses RecentChatsList) */
    compact?: boolean;
    /** Project filter - "all" for all projects, project name to filter */
    projectFilter?: string;
}

export const ChatSessions: React.FC<ChatSessionsProps> = ({ maxItems, onShowAll, compact = false, projectFilter = "all" }) => {
    const { persistenceEnabled } = useConfigContext();
    const { sessionName } = useChatContext();
    const { projects } = useProjectContext();

    if (persistenceEnabled) {
        // Use compact RecentChatsList when in compact mode
        if (compact) {
            return <RecentChatsList maxItems={maxItems} onShowAll={onShowAll} projectFilter={projectFilter} />;
        }
        // Use full SessionList - it has its own search/filter UI
        return <SessionList projects={projects} />;
    }

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
