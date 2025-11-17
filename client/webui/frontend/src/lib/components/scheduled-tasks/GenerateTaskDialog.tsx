import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, Button, Textarea, Badge } from '@/lib/components/ui';
import { MessageBanner } from '@/lib/components/common';
import { Calendar, Clock, Repeat, Sparkles } from 'lucide-react';

interface GenerateTaskDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onGenerate: (taskDescription: string) => void;
}

const QUICK_SUGGESTIONS = [
    { icon: Calendar, label: 'Generate daily report at 9 AM' },
    { icon: Clock, label: 'Check system health every 30 minutes' },
    { icon: Repeat, label: 'Clean up old data weekly' },
];

export const GenerateTaskDialog: React.FC<GenerateTaskDialogProps> = ({
    isOpen,
    onClose,
    onGenerate,
}) => {
    const [taskDescription, setTaskDescription] = useState('');
    const [showError, setShowError] = useState(false);

    const handleGenerate = () => {
        if (!taskDescription.trim()) {
            setShowError(true);
            return;
        }
        setShowError(false);
        onGenerate(taskDescription.trim());
        setTaskDescription('');
    };

    const handleSuggestionClick = (suggestion: string) => {
        setTaskDescription(suggestion);
    };

    const handleClose = () => {
        setTaskDescription('');
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
                    <DialogTitle className="text-xl">Create Scheduled Task</DialogTitle>
                    <DialogDescription className="text-base">
                        Describe what you want to automate and when it should run. The AI will help you configure the task details.
                    </DialogDescription>
                </DialogHeader>

                {showError && (
                    <MessageBanner
                        variant="error"
                        message="Please describe your task before generating."
                        dismissible
                        onDismiss={() => setShowError(false)}
                    />
                )}

                <div className="space-y-4 py-4">
                    <Textarea
                        placeholder="e.g., 'Generate a daily report at 9 AM' or 'Check system health every 30 minutes'"
                        value={taskDescription}
                        onChange={handleTextChange}
                        rows={6}
                        className="resize-none"
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                handleGenerate();
                            }
                        }}
                    />

                    {/* Quick Suggestions */}
                    <div className="flex flex-wrap gap-2">
                        {QUICK_SUGGESTIONS.map((suggestion, index) => {
                            const Icon = suggestion.icon;
                            return (
                                <Badge
                                    key={index}
                                    variant="outline"
                                    className="cursor-pointer hover:bg-primary/10 transition-colors px-3 py-1.5"
                                    onClick={() => handleSuggestionClick(suggestion.label)}
                                >
                                    <Icon className="h-3 w-3 mr-1.5" />
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
                    <Button
                        onClick={handleGenerate}
                    >
                        <Sparkles className="h-4 w-4 mr-2" />
                        Generate
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};