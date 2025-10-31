import React, { useState, useEffect } from "react";
import { Pencil, Save, X } from "lucide-react";

import { Button, Textarea } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";

interface ProjectDescriptionProps {
    project: Project;
    isEditing: boolean;
    onToggleEdit: () => void;
    onSave: (description: string) => Promise<void>;
    isSaving: boolean;
}

export const ProjectDescription: React.FC<ProjectDescriptionProps> = ({
    project,
    isEditing,
    onToggleEdit,
    onSave,
    isSaving,
}) => {
    const [editedDescription, setEditedDescription] = useState(project.description || "");

    useEffect(() => {
        setEditedDescription(project.description || "");
    }, [project.description]);

    const handleSave = async () => {
        if (editedDescription.trim() !== (project.description || "")) {
            await onSave(editedDescription.trim());
        } else {
            onToggleEdit();
        }
    };

    const handleCancel = () => {
        setEditedDescription(project.description || "");
        onToggleEdit();
    };

    return (
        <div className="px-6 py-4 border-b">
            <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-semibold text-foreground">Description</h3>
                {!isEditing && (
                    <Button variant="ghost" size="sm" onClick={onToggleEdit} className="h-8 w-8 p-0" tooltip="Edit">
                        <Pencil className="h-4 w-4" />
                    </Button>
                )}
            </div>
            {isEditing ? (
                <div className="space-y-2">
                    <Textarea
                        value={editedDescription}
                        onChange={(e) => setEditedDescription(e.target.value)}
                        placeholder="Add a description for this project..."
                        rows={3}
                        disabled={isSaving}
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
                <div className={`text-sm text-muted-foreground ${!project.description ? 'rounded-md bg-muted p-3 text-center' : ''}`}>
                    {project.description || "No description provided."}
                </div>
            )}
        </div>
    );
};
