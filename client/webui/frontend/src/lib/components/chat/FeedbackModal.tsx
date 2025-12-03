import React, { useState, useRef, useEffect } from "react";

import { Button, Textarea } from "@/lib/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";

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
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[750px]" showCloseButton={false}>
                <DialogHeader>
                    <DialogTitle>Provide Feedback</DialogTitle>
                    <DialogDescription className="flex flex-col gap-2">
                        <span>{feedbackPrompt}</span>
                        <span>Providing more details will help improve AI responses over time.</span>
                    </DialogDescription>
                </DialogHeader>
                <div className="flex flex-col gap-2">
                    <Textarea ref={textareaRef} value={feedbackText} onChange={e => setFeedbackText(e.target.value)} className="min-h-[120px] text-sm" disabled={isSubmitting} />
                    <p className="text-muted-foreground text-xs">Along with your feedback, details of the task will be recorded.</p>
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={handleClose} disabled={isSubmitting}>
                        Cancel
                    </Button>
                    <Button variant="default" onClick={handleSubmit} disabled={isSubmitting}>
                        Submit
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
});
