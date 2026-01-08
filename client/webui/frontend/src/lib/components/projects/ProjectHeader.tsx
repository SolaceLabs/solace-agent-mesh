import React, { useState, useEffect } from "react";
import { Pencil, Save, X } from "lucide-react";

import { Button, Input } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";

interface ProjectHeaderProps {
    project: Project;
    isEditing: boolean;
    onToggleEdit: () => void;
    onSave: (name: string) => Promise<void>;
    isSaving: boolean;
    error?: string | null;
}

export const ProjectHeader: React.FC<ProjectHeaderProps> = ({
    project,
    isEditing,
    onToggleEdit,
    onSave,
    isSaving,
    error,
}) => {
    const [editedName, setEditedName] = useState(project.name);

    useEffect(() => {
        setEditedName(project.name);
    }, [project.name]);

    const handleSave = async () => {
        if (editedName.trim() && editedName.trim() !== project.name) {
            await onSave(editedName.trim());
        } else {
            onToggleEdit();
        }
    };

    const handleCancel = () => {
        setEditedName(project.name);
        onToggleEdit();
    };

    return (
        <div className="border-b px-6 py-4">
            <div className="flex items-center justify-between">
                {isEditing ? (
                    <div className="flex flex-col gap-2 flex-1">
                        <div className="flex items-center gap-2">
                            <Input
                                value={editedName}
                                onChange={(e) => setEditedName(e.target.value)}
                                className="text-2xl font-bold"
                                disabled={isSaving}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                        handleSave();
                                    } else if (e.key === "Escape") {
                                        handleCancel();
                                    }
                                }}
                            />
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleSave}
                                disabled={isSaving || !editedName.trim()}
                            >
                                <Save className="h-4 w-4" />
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleCancel}
                                disabled={isSaving}
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                        {error && (
                            <p className="text-sm text-destructive">{error}</p>
                        )}
                    </div>
                ) : (
                    <>
                        <h1 className="text-2xl font-bold text-foreground">{project.name}</h1>
                        <Button variant="ghost" size="sm" onClick={onToggleEdit} className="h-8 w-8 p-0" tooltip="Edit">
                            <Pencil className="h-4 w-4" />
                        </Button>
                    </>
                )}
            </div>
        </div>
    );
};
