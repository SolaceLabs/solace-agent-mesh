import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, Button, Textarea, Badge } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { FileText, Mail, Code, Sparkles } from "lucide-react";

interface GeneratePromptDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onGenerate: (taskDescription: string) => void;
}

const QUICK_SUGGESTIONS = [
    { icon: FileText, label: "Summarize a document" },
    { icon: Mail, label: "Write me an email" },
    { icon: Code, label: "Translate code" },
];

export const GeneratePromptDialog: React.FC<GeneratePromptDialogProps> = ({ isOpen, onClose, onGenerate }) => {
    const [taskDescription, setTaskDescription] = useState("");
    const [showError, setShowError] = useState(false);

    const handleGenerate = () => {
        if (!taskDescription.trim()) {
            setShowError(true);
            return;
        }
        setShowError(false);
        onGenerate(taskDescription.trim());
        setTaskDescription("");
    };

    const handleSuggestionClick = (suggestion: string) => {
        setTaskDescription(suggestion);
    };

    const handleClose = () => {
        setTaskDescription("");
        setShowError(false);
        onClose();
    };

    const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setTaskDescription(e.target.value);
        if (showError && e.target.value.trim()) {
            setShowError(false);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={() => {}}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle className="text-xl">Create Prompt</DialogTitle>
                    <DialogDescription className="text-base">
                        You can generate a prompt by sharing basic details about your task. Alternatively, paste in an existing prompt and the AI will convert it into a re-usable prompt for you.
                    </DialogDescription>
                </DialogHeader>

                {showError && <MessageBanner variant="error" message="Please describe your task before generating a prompt." dismissible onDismiss={() => setShowError(false)} />}

                <div className="space-y-4 py-4">
                    <Textarea
                        placeholder="Describe your task..."
                        value={taskDescription}
                        onChange={handleTextChange}
                        rows={6}
                        className="resize-none"
                        onKeyDown={e => {
                            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                handleGenerate();
                            }
                        }}
                    />

                    {/* Quick Suggestions */}
                    <div className="flex flex-wrap gap-2">
                        {QUICK_SUGGESTIONS.map((suggestion, index) => {
                            const Icon = suggestion.icon;
                            return (
                                <Badge key={index} variant="outline" className="hover:bg-primary/10 cursor-pointer px-3 py-1.5 transition-colors" onClick={() => handleSuggestionClick(suggestion.label)}>
                                    <Icon className="mr-1.5 h-3 w-3" />
                                    {suggestion.label}
                                </Badge>
                            );
                        })}
                    </div>
                </div>

                <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button data-testid="generatePromptButton" onClick={handleGenerate}>
                        <Sparkles className="mr-2 h-4 w-4" />
                        Generate
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
