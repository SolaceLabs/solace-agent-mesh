import React from "react";

import { useSessionPreview } from "@/lib/hooks";

export const ChatSessions: React.FC = () => {
    const sessionPreview = useSessionPreview();

    return (
        <div className="flex h-full flex-col">
            <div className="flex-1 overflow-y-auto px-4">
                {/* Current Session */}
                <div className="bg-accent/50 hover:bg-accent mb-3 cursor-pointer rounded-md p-3">
                    <div className="text-foreground truncate text-sm font-medium text-nowrap">{sessionPreview}</div>
                    <div className="text-muted-foreground mt-1 text-xs">Current session</div>
                </div>
                
                {/* Multi-session notice */}
                <div className="text-muted-foreground mt-4 text-center text-xs">
                    Multi-session support coming soon
                </div>
            </div>
        </div>
    );
};
