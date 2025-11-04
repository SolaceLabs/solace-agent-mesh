import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, Button, Textarea, Badge } from '@/lib/components/ui';
import { X, FileText, Mail, Code } from 'lucide-react';

interface GeneratePromptDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onGenerate: (taskDescription: string) => void;
}

const QUICK_SUGGESTIONS = [
    { icon: FileText, label: 'Summarize a document' },
    { icon: Mail, label: 'Write me an email' },
    { icon: Code, label: 'Translate code' },
];

export const GeneratePromptDialog: React.FC<GeneratePromptDialogProps> = ({
    isOpen,
    onClose,
    onGenerate,
}) => {
    const [taskDescription, setTaskDescription] = useState('');

    const handleGenerate = () => {
        if (taskDescription.trim()) {
            onGenerate(taskDescription.trim());
            setTaskDescription('');
        }
    };

    const handleSuggestionClick = (suggestion: string) => {
        setTaskDescription(suggestion);
    };

    const handleClose = () => {
        setTaskDescription('');
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <div className="flex items-center justify-between">
                        <DialogTitle className="text-xl">Generate a prompt</DialogTitle>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleClose}
                            className="h-6 w-6"
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                    <DialogDescription className="text-base">
                        You can generate a prompt template by sharing basic details about your task.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <Textarea
                        placeholder="Describe your task..."
                        value={taskDescription}
                        onChange={(e) => setTaskDescription(e.target.value)}
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
                    <Button variant="outline" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleGenerate}
                        disabled={!taskDescription.trim()}
                    >
                        Generate
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};