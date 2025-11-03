import { useChatContext, useConfigContext } from "@/lib/hooks";
import { Edit } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogClose, DialogTrigger, DialogFooter } from "@/lib/components/ui/";
import { Button } from "@/lib/components/ui/button";

interface NewChatButtonProps {
    text?: string;
    onClick?: () => void;
}

const NewChatButton: React.FC<NewChatButtonProps> = ({ text, onClick }) => {
    return (
        <Button data-testid="startNewChat" variant="ghost" onClick={onClick} tooltip="Start New Chat Session">
            <Edit className="size-5" />
            {text}
        </Button>
    );
};

interface ChatSessionDialogProps {
    buttonText?: string;
}
export const ChatSessionDialog: React.FC<ChatSessionDialogProps> = ({ buttonText }) => {
    const { handleNewSession } = useChatContext();
    const { persistenceEnabled } = useConfigContext();

    return persistenceEnabled ? (
        <NewChatButton text={buttonText} onClick={() => handleNewSession()} />
    ) : (
        <Dialog>
            <DialogTrigger asChild>
                <NewChatButton text={buttonText} />
            </DialogTrigger>

            <DialogContent>
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">New Chat Session?</DialogTitle>
                    <DialogDescription className="flex flex-col gap-2">Starting a new chat session will clear the current chat history and files. Are you sure you want to proceed?</DialogDescription>
                </DialogHeader>

                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="ghost">Cancel</Button>
                    </DialogClose>

                    <DialogClose asChild>
                        <Button variant="default" onClick={() => handleNewSession()}>
                            Start New Chat
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
