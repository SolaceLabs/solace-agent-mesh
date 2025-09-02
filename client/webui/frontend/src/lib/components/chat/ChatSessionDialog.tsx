import React from "react";

import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";

interface ChatSessionDialogProps {
    isOpen: boolean;
    onClose: () => void;
}

export const ChatSessionDialog: React.FC<ChatSessionDialogProps> = ({ isOpen, onClose }) => {
	const { handleNewSession } = useChatContext();

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle className="flex flex-row gap-1 max-w-[400px]">
						Start New Chat Session?
                    </DialogTitle>
                    <DialogDescription className="flex flex-col gap-2">
                        This will create a new chat session. Your current chat will be saved in the sessions panel.
                    </DialogDescription>
                </DialogHeader>
                <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button variant="default" onClick={() => {
						handleNewSession();
						onClose();
					}}>
                        Start New Chat
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
