import React, { useState, useRef, useEffect } from "react";

import { Textarea } from "@/lib/components/ui";
import { ConfirmationDialog } from "../common";

interface FeedbackModalProps {
    isOpen: boolean;
    onClose: () => void;
    feedbackType: "up" | "down";
    onSubmit: (feedbackText: string) => Promise<void>;
}

export const FeedbackModal = React.memo<FeedbackModalProps>(({ isOpen, onClose, feedbackType, onSubmit }) => {
    const [feedbackText, setFeedbackText] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        if (isOpen) {
            // Reset state when modal opens
            setFeedbackText("");
            setIsSubmitting(false);
            // Focus textarea after a brief delay to ensure modal is rendered
            setTimeout(() => {
                textareaRef.current?.focus();
            }, 100);
        }
    }, [isOpen]);

    const handleSubmit = async () => {
        setIsSubmitting(true);
        try {
            await onSubmit(feedbackText);
            onClose();
        } catch {
            // Error handling is done in the parent component
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            onClose();
        }
    };

    const feedbackPrompt = feedbackType === "up" ? "What did you like about the response?" : "What did you dislike about the response?";

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={open => !open && handleClose()}
            onConfirm={handleSubmit}
            onCancel={handleClose}
            title="Provide Feedback"
            description={`${feedbackPrompt} Providing more details will help improve AI responses over time.`}
            content={
                <div className="flex flex-col gap-2">
                    <Textarea ref={textareaRef} value={feedbackText} onChange={e => setFeedbackText(e.target.value)} className="min-h-[120px] text-sm" disabled={isSubmitting} />
                    <p className="text-muted-foreground text-xs">Along with your feedback, details of the task will be recorded.</p>
                </div>
            }
            actionLabels={{ confirm: "Submit" }}
        />
    );
});
