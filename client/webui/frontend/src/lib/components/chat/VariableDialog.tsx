/**
 * Modal dialog for substituting variables in prompts
 */

import React, { useState, useEffect } from 'react';
import type { PromptGroup } from '@/lib/types/prompts';
import { detectVariables, replaceVariables } from '@/lib/utils/promptUtils';
import { Button } from '@/lib/components/ui';
import { MessageBanner } from '@/lib/components/common';

interface VariableDialogProps {
    group: PromptGroup;
    onSubmit: (processedPrompt: string) => void;
    onClose: () => void;
}

export const VariableDialog: React.FC<VariableDialogProps> = ({
    group,
    onSubmit,
    onClose,
}) => {
    const promptText = group.production_prompt?.prompt_text || '';
    const variables = detectVariables(promptText);
    
    const [values, setValues] = useState<Record<string, string>>(() => {
        const initial: Record<string, string> = {};
        variables.forEach(v => {
            initial[v] = '';
        });
        return initial;
    });
    const [showError, setShowError] = useState(false);

    // Handle form submission
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        
        // Check if all variables have values
        const allFilled = variables.every(v => values[v]?.trim());
        if (!allFilled) {
            setShowError(true);
            setTimeout(() => setShowError(false), 3000);
            return;
        }
        
        const processedPrompt = replaceVariables(promptText, values);
        onSubmit(processedPrompt);
    };

    // Handle escape key
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };
        
        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [onClose]);


    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="w-full max-w-lg rounded-lg border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
                {/* Header */}
                <div className="mb-4">
                    <h2 className="text-lg font-semibold">Fill in Variables</h2>
                    <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                        {group.name}
                    </p>
                </div>

                {/* Error Banner */}
                {showError && (
                    <MessageBanner
                        variant="error"
                        message="Please fill in all variables before inserting the prompt"
                    />
                )}

                {/* Form */}
                <form onSubmit={handleSubmit}>
                    <div className="space-y-4">
                        {variables.map((variable) => (
                            <div key={variable}>
                                <label 
                                    htmlFor={`var-${variable}`}
                                    className="block text-sm font-medium mb-1"
                                >
                                    {variable}
                                </label>
                                <textarea
                                    id={`var-${variable}`}
                                    value={values[variable]}
                                    onChange={(e) => setValues(prev => ({
                                        ...prev,
                                        [variable]: e.target.value
                                    }))}
                                    className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] min-h-[80px]"
                                    placeholder={`Enter value for ${variable}...`}
                                    required
                                />
                            </div>
                        ))}
                    </div>

                    {/* Actions */}
                    <div className="mt-6 flex justify-end gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onClose}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                        >
                            Insert Prompt
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    );
};