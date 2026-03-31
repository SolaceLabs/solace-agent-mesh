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
                <div className="mb-3 cursor-pointer rounded-md bg-(--secondary-w20) p-3 hover:bg-(--secondary-w40)">
                    <div className="truncate text-sm font-medium text-nowrap text-(--primary-text-wMain)">{sessionName || "New Chat"}</div>
                    <div className="mt-1 text-xs text-(--secondary-text-wMain)">Current session</div>
                </div>

                {/* Multi-session notice */}
                <div className="mt-4 text-center text-xs text-(--secondary-text-wMain)">Persistence is not enabled.</div>
            </div>
        </div>
    );
};
