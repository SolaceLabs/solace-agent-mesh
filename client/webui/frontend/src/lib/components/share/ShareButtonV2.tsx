/**
 * ShareButtonV2 component - Button to open redesigned share dialog V2
 */

import { useState } from "react";
import { Share2 } from "lucide-react";
import { Button } from "../ui/button";
import { ShareDialogV2 } from "./ShareDialogV2";
import { useChatContext } from "@/lib/hooks";

interface ShareButtonV2Props {
    sessionId: string;
    sessionTitle: string;
    className?: string;
}

export function ShareButtonV2({ sessionId, sessionTitle, className }: Readonly<ShareButtonV2Props>) {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const { displayError, addNotification } = useChatContext();

    return (
        <>
            <Button variant="ghost" size="sm" onClick={() => setIsDialogOpen(true)} className={className} title="Share this session (V2)">
                <Share2 className="h-4 w-4" />
                <span className="ml-2 hidden sm:inline">Share V2</span>
            </Button>

            <ShareDialogV2
                sessionId={sessionId}
                sessionTitle={sessionTitle}
                open={isDialogOpen}
                onOpenChange={setIsDialogOpen}
                onError={error => displayError({ title: error.title, error: error.message })}
                onSuccess={message => addNotification(message, "success")}
            />
        </>
    );
}
