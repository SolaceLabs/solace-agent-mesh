import React, { useState, useEffect } from "react";
import { Pencil, Save, X } from "lucide-react";

import { Button, Textarea } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";

interface SystemPromptSectionProps {
    project: Project;
    onSave: (systemPrompt: string) => Promise<void>;
    isSaving: boolean;
}

export const SystemPromptSection: React.FC<SystemPromptSectionProps> = ({
    project,
    onSave,
    isSaving,
}) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editedPrompt, setEditedPrompt] = useState(project.systemPrompt || "");

    useEffect(() => {
        setEditedPrompt(project.systemPrompt || "");
    }, [project.systemPrompt]);

    const handleSave = async () => {
        if (editedPrompt.trim() !== (project.systemPrompt || "")) {
            await onSave(editedPrompt.trim());
        }
        setIsEditing(false);
    };

    const handleCancel = () => {
        setEditedPrompt(project.systemPrompt || "");
        setIsEditing(false);
    };

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
                        <Textarea
                            value={editedPrompt}
                            onChange={(e) => setEditedPrompt(e.target.value)}
                            placeholder="Add instructions for this project..."
                            rows={8}
                            disabled={isSaving}
                            className="text-sm"
                        />
                        <div className="flex gap-2">
                            <Button
                                size="sm"
                                onClick={handleSave}
                                disabled={isSaving}
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
