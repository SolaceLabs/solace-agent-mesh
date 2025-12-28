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

export const SystemPromptSection: React.FC<SystemPromptSectionProps> = ({ project, onSave, isSaving, error }) => {
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    return (
        <>
            <div className="mb-6">
                <div className="mb-3 flex items-center justify-between px-4 pt-4">
                    <h3 className="text-foreground text-sm font-semibold">Instructions</h3>
                    <Button variant="ghost" size="sm" onClick={() => setIsDialogOpen(true)} className="h-8 w-8 p-0" tooltip="Edit">
                        <Pencil className="h-4 w-4" />
                    </Button>
                </div>

                <div className="px-4">
                    <div className={`text-muted-foreground bg-muted max-h-[400px] min-h-[120px] overflow-y-auto rounded-md p-3 text-sm whitespace-pre-wrap ${!project.systemPrompt ? "flex items-center justify-center" : ""}`}>
                        {project.systemPrompt || "No instructions. Provide instructions to tailor the chat responses to your needs."}
                    </div>
                </div>
            </div>

            <EditInstructionsDialog isOpen={isDialogOpen} onClose={() => setIsDialogOpen(false)} onSave={onSave} project={project} isSaving={isSaving} error={error} />
        </>
    );
};
