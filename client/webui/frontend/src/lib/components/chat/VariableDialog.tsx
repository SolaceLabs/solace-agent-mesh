/**
 * Modal dialog for substituting variables in prompts
 */

import React, { useState, useEffect } from "react";
import type { PromptGroup } from "@/lib/types/prompts";
import { detectVariables, replaceVariables } from "@/lib/utils/promptUtils";
import { Button } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";

interface VariableDialogProps {
    group: PromptGroup;
    onSubmit: (processedPrompt: string) => void;
    onClose: () => void;
}

export const VariableDialog: React.FC<VariableDialogProps> = ({ group, onSubmit, onClose }) => {
    const promptText = group.productionPrompt?.promptText || "";
    const variables = detectVariables(promptText);

    const [values, setValues] = useState<Record<string, string>>(() => {
        const initial: Record<string, string> = {};
        variables.forEach(v => {
            initial[v] = "";
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
            if (e.key === "Escape") {
                onClose();
            }
        };

        window.addEventListener("keydown", handleEscape);
        return () => window.removeEventListener("keydown", handleEscape);
    }, [onClose]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-lg border border-[var(--border)] bg-[var(--background)] shadow-lg">
                {/* Header - Fixed */}
                <div className="flex-shrink-0 p-6 pb-4">
                    <h2 className="text-lg font-semibold">Insert {group.name}</h2>
                    <p className="mt-1 text-sm text-[var(--muted-foreground)]">Variables represent placeholder information in the template. Enter a value for each placeholder below.</p>
                </div>

                {showError && (
                    <div className="flex-shrink-0 px-6">
                        <MessageBanner variant="error" message="Please fill in all variables before inserting the prompt" />
                    </div>
                )}

                <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
                    <div className="flex-1 overflow-y-auto px-6 py-4">
                        <div className="space-y-4">
                            {variables.map(variable => (
                                <div key={variable}>
                                    <label htmlFor={`var-${variable}`} className="mb-1 block text-sm font-medium">
                                        {variable}
                                    </label>
                                    <textarea
                                        id={`var-${variable}`}
                                        value={values[variable]}
                                        onChange={e =>
                                            setValues(prev => ({
                                                ...prev,
                                                [variable]: e.target.value,
                                            }))
                                        }
                                        className="min-h-[80px] w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
                                        required
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="flex flex-shrink-0 justify-end gap-2 border-t border-[var(--border)] p-6 pt-4">
                        <Button type="button" variant="ghost" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit">Insert Prompt</Button>
                    </div>
                </form>
            </div>
        </div>
    );
};
