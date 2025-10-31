import React, { useState, useEffect } from "react";
import { Pencil, Save, X, AlertCircle } from "lucide-react";

import { Button, Textarea } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { useConfigContext } from "@/lib/hooks";

interface SystemPromptSectionProps {
    project: Project;
    onSave: (systemPrompt: string) => Promise<void>;
    isSaving: boolean;
    error?: string | null;
}

export const SystemPromptSection: React.FC<SystemPromptSectionProps> = ({
    project,
    onSave,
    isSaving,
    error,
}) => {
    const { validationLimits } = useConfigContext();
    const MAX_INSTRUCTIONS_LENGTH = validationLimits?.projectInstructionsMax ?? 4000;
    
    const [isEditing, setIsEditing] = useState(false);
    const [editedPrompt, setEditedPrompt] = useState(project.systemPrompt || "");
    const [localError, setLocalError] = useState<string | null>(null);

    useEffect(() => {
        setEditedPrompt(project.systemPrompt || "");
        setLocalError(null);
    }, [project.systemPrompt]);

    useEffect(() => {
        if (error) {
            setLocalError(error);
        }
    }, [error]);

    const handleSave = async () => {
        setLocalError(null);

        if (editedPrompt.trim() !== (project.systemPrompt || "")) {
            try {
                await onSave(editedPrompt.trim());
                setIsEditing(false);
            } catch {
                // Error will be handled by parent component
            }
        } else {
            setIsEditing(false);
        }
    };

    const handleCancel = () => {
        setEditedPrompt(project.systemPrompt || "");
        setLocalError(null);
        setIsEditing(false);
    };

    const characterCount = editedPrompt.length;
    const isOverLimit = characterCount > MAX_INSTRUCTIONS_LENGTH;
    const isNearLimit = characterCount > MAX_INSTRUCTIONS_LENGTH * 0.9;

    return (
        <div className="border-b">
            <div className="flex items-center justify-between px-4 py-3">
                <h3 className="text-sm font-semibold text-foreground">Instructions</h3>
                {!isEditing && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsEditing(true)}
                        className="h-8 w-8 p-0"
                        tooltip="Edit"
                    >
                        <Pencil className="h-4 w-4" />
                    </Button>
                )}
            </div>

            <div className="px-4 pb-3">
                {isEditing ? (
                    <div className="space-y-2">
                        <div className="relative">
                            <Textarea
                                value={editedPrompt}
                                onChange={(e) => setEditedPrompt(e.target.value)}
                                placeholder="Add instructions for this project..."
                                rows={8}
                                disabled={isSaving}
                                className={`text-sm ${isOverLimit ? 'border-destructive focus-visible:ring-destructive' : ''}`}
                            />
                            <div className={`mt-1 text-xs ${isOverLimit ? 'text-destructive font-medium' : isNearLimit ? 'text-orange-500' : 'text-muted-foreground'}`}>
                                {isOverLimit
                                    ? `Instructions must be less than ${MAX_INSTRUCTIONS_LENGTH} characters (currently ${characterCount})`
                                    : `${characterCount} / ${MAX_INSTRUCTIONS_LENGTH} characters`
                                }
                            </div>
                        </div>
                        {localError && (
                            <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                <span>{localError}</span>
                            </div>
                        )}
                        <div className="flex gap-2">
                            <Button
                                size="sm"
                                onClick={handleSave}
                                disabled={isSaving || isOverLimit}
                            >
                                <Save className="h-4 w-4 mr-2" />
                                Save
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleCancel}
                                disabled={isSaving}
                            >
                                <X className="h-4 w-4 mr-2" />
                                Cancel
                            </Button>
                        </div>
                    </div>
                ) : (
                    <div className={`text-sm text-muted-foreground whitespace-pre-wrap rounded-md bg-muted p-3 min-h-[120px] max-h-[400px] overflow-y-auto ${!project.systemPrompt ? 'flex items-center justify-center' : ''}`}>
                        {project.systemPrompt || "No instructions provided."}
                    </div>
                )}
            </div>
        </div>
    );
};
