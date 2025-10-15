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
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">New Chat Session?</DialogTitle>
                    <DialogDescription className="flex flex-col gap-2">Starting a new chat session will clear the current chat history and files. Are you sure you want to proceed?</DialogDescription>
                </DialogHeader>
                <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button
                        variant="default"
                        onClick={() => {
                            handleNewSession();
                            onClose();
                        }}
                    >
                        Start New Chat
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
