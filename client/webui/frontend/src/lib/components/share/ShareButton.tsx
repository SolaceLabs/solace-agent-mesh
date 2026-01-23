/**
 * ShareButton component - Button to open share dialog
 */

import { useState } from "react";
import { Share2 } from "lucide-react";
import { Button } from "../ui/button";
import { ShareDialog } from "./ShareDialog";

interface ShareButtonProps {
    sessionId: string;
    sessionTitle: string;
    className?: string;
}

export function ShareButton({ sessionId, sessionTitle, className }: ShareButtonProps) {
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    return (
        <>
            <Button variant="ghost" size="sm" onClick={() => setIsDialogOpen(true)} className={className} title="Share this session">
                <Share2 className="h-4 w-4" />
                <span className="ml-2 hidden sm:inline">Share</span>
            </Button>

            <ShareDialog sessionId={sessionId} sessionTitle={sessionTitle} open={isDialogOpen} onOpenChange={setIsDialogOpen} />
        </>
    );
}
