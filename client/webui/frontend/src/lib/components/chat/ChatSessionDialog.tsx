import { useChatContext, useConfigContext } from "@/lib/hooks";
import { Edit } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogClose, DialogTrigger } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";

interface ChatSessionDialogProps {
    buttonText?: string;
}

export const ChatSessionDialog: React.FC<ChatSessionDialogProps> = ({ buttonText }) => {
    const { handleNewSession } = useChatContext();
    const { persistenceEnabled } = useConfigContext();

    return persistenceEnabled ? (
        <Button variant="ghost" onClick={handleNewSession} tooltip="Start New Chat Session">
            <Edit className="size-5" />
            {buttonText}
        </Button>
    ) : (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="ghost" tooltip="Start New Chat Session">
                    <Edit className="size-5" />
                    {buttonText}
                </Button>
            </DialogTrigger>

            <DialogContent>
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">New Chat Session?</DialogTitle>
                    <DialogDescription className="flex flex-col gap-2">Starting a new chat session will clear the current chat history and files. Are you sure you want to proceed?</DialogDescription>
                </DialogHeader>

                <div className="flex justify-end gap-2">
                    <DialogClose asChild>
                        <Button variant="ghost">Cancel</Button>
                    </DialogClose>

                    <DialogClose asChild>
                        <Button variant="default" onClick={handleNewSession}>
                            Start New Chat
                        </Button>
                    </DialogClose>
                </div>
            </DialogContent>
        </Dialog>
    );
};
