import { useState } from "react";
import { Pencil } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { useIsProjectOwner } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";
import { EditInstructionsDialog } from "./EditInstructionsDialog";

interface SystemPromptSectionProps {
    project: Project;
    onSave: (systemPrompt: string) => Promise<void>;
    isSaving: boolean;
    isDisabled?: boolean;
    error?: string | null;
}

export const SystemPromptSection = ({ project, onSave, isSaving, isDisabled, error }: SystemPromptSectionProps) => {
    const isOwner = useIsProjectOwner(project.userId);
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    return (
        <>
            <div className="mb-6">
                <div className="mb-3 flex items-center justify-between px-4 pt-4">
                    <h3 className="text-foreground text-sm font-semibold">Instructions</h3>
                    {isOwner && (
                        <Button variant="ghost" size="sm" testid="editInstructions" onClick={() => setIsDialogOpen(true)} className="h-8 w-8 p-0" tooltip="Edit" disabled={isDisabled}>
                            <Pencil className="h-4 w-4" />
                        </Button>
                    )}
                </div>

                <div className="px-4">
                    <div className={`text-muted-foreground bg-muted max-h-[240px] min-h-[120px] overflow-y-auto rounded-md p-3 text-sm whitespace-pre-wrap ${!project.systemPrompt ? "flex items-center justify-center" : ""}`}>
                        {project.systemPrompt || "No instructions. Provide instructions to tailor the chat responses to your needs."}
                    </div>
                </div>
            </div>

            <EditInstructionsDialog isOpen={isDialogOpen} onClose={() => setIsDialogOpen(false)} onSave={onSave} project={project} isSaving={isSaving} error={error} />
        </>
    );
};
