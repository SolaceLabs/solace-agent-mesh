import React, { useState } from "react";
import { Pencil } from "lucide-react";

import { Button } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { EditInstructionsDialog } from "./EditInstructionsDialog";

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
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    return (
        <>
            <div className="mb-6">
                <div className="flex items-center justify-between px-4 mb-3">
                    <h3 className="text-sm font-semibold text-foreground">Instructions</h3>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsDialogOpen(true)}
                        className="h-8 w-8 p-0"
                        tooltip="Edit"
                    >
                        <Pencil className="h-4 w-4" />
                    </Button>
                </div>

                <div className="px-4">
                    <div className={`text-sm text-muted-foreground whitespace-pre-wrap rounded-md bg-muted p-3 min-h-[120px] max-h-[400px] overflow-y-auto ${!project.systemPrompt ? 'flex items-center justify-center' : ''}`}>
                        {project.systemPrompt || "No instructions provided."}
                    </div>
                </div>
            </div>

            <EditInstructionsDialog
                isOpen={isDialogOpen}
                onClose={() => setIsDialogOpen(false)}
                onSave={onSave}
                project={project}
                isSaving={isSaving}
                error={error}
            />
        </>
    );
};
