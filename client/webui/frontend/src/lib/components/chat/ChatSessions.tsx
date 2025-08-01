import { SessionList } from "./SessionList";

export const ChatSessions = () => {
    return (
        <div className="flex h-full flex-col">
            <div className="flex-1 overflow-y-auto px-4">
                <SessionList />
            </div>
        </div>
    );
};
