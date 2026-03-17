/**
 * ShareButton component - Button to open share dialog
 */

import { useState } from "react";
import { Share2 } from "lucide-react";
import { Button } from "../ui/button";
import { ShareDialog } from "./ShareDialog";
import { useChatContext } from "@/lib/hooks";

interface ShareButtonProps {
    sessionId: string;
    sessionTitle: string;
    /** ISO timestamp of when the session was last updated (optional) */
    sessionUpdatedTime?: string;
    className?: string;
}

export function ShareButton({ sessionId, sessionTitle, sessionUpdatedTime, className }: Readonly<ShareButtonProps>) {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const { displayError, addNotification } = useChatContext();

    return (
        <>
            <Button variant="ghost" size="sm" onClick={() => setIsDialogOpen(true)} className={className} title="Share this session">
                <Share2 className="h-4 w-4" />
                <span className="ml-2 hidden sm:inline">Share</span>
            </Button>

            <ShareDialog
                sessionId={sessionId}
                sessionTitle={sessionTitle}
                sessionUpdatedTime={sessionUpdatedTime}
                open={isDialogOpen}
                onOpenChange={setIsDialogOpen}
                onError={error => displayError({ title: error.title, error: error.message })}
                onSuccess={message => addNotification(message, "success")}
            />
        </>
    );
}
