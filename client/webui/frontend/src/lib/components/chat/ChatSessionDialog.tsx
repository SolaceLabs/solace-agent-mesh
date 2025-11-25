import { useChatContext, useConfigContext } from "@/lib/hooks";
import { Edit } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import { useState } from "react";

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
    const [isOpen, setIsOpen] = useState(false);

    return persistenceEnabled ? (
        <NewChatButton text={buttonText} onClick={() => handleNewSession()} />
    ) : (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={setIsOpen}
            title="Start New Chat Session"
            description="Starting a new chat session will clear the current chat history and files. Are you sure you want to proceed?"
            actionLabels={{ confirm: "Start New Chat" }}
            onConfirm={handleNewSession}
            trigger={<NewChatButton text={buttonText} />}
        />
    );
};
