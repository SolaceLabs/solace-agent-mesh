import React from "react";
import { Plus, Sparkles } from "lucide-react";

import { useConfigContext } from "@/lib/hooks";
import { GridCard } from "@/lib/components/common";
import { Button } from "@/lib/components/ui";

interface CreatePromptCardProps {
    onManualCreate: () => void;
    onAIAssisted: () => void;
    isCentered?: boolean;
}

export const CreatePromptCard: React.FC<CreatePromptCardProps> = ({ onManualCreate, onAIAssisted, isCentered = false }) => {
    const { configFeatureEnablement } = useConfigContext();
    const aiAssistedEnabled = configFeatureEnablement?.promptAIAssisted ?? true;

    if (isCentered) {
        // Enhanced centered version for empty state
        return (
            <div className="w-full max-w-[480px] p-8">
                <div className="flex h-full w-full flex-col items-center justify-center gap-6">
                    {/* Title and description */}
                    <div className="flex flex-col items-center gap-2">
                        <h2 className="text-foreground text-2xl font-semibold">Create New Prompt</h2>
                        <p className="text-muted-foreground text-sm">Choose how you'd like to create your prompt</p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex w-full max-w-[320px] flex-col gap-3">
                        <Button data-testid="buildWithAIButton" onClick={onAIAssisted} disabled={!aiAssistedEnabled} variant="default" size="lg" className="w-full">
                            <Sparkles className="mr-2 h-4 w-4" />
                            Build with AI
                            {!aiAssistedEnabled && <span className="ml-1 text-xs">(Disabled)</span>}
                        </Button>

                        <Button onClick={onManualCreate} variant="outline" size="lg" className="w-full">
                            <Plus className="mr-2 h-4 w-4" />
                            Create Manually
                        </Button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <GridCard className="border border-dashed border-[var(--color-primary-wMain)]">
            <div className="flex h-full w-full flex-col items-center justify-center gap-4 p-6">
                <h3 className="text-center text-lg font-semibold">Create New Prompt</h3>

                <div className="flex w-full max-w-[240px] flex-col gap-3">
                    <Button data-testid="buildWithAIButton" onClick={onAIAssisted} disabled={!aiAssistedEnabled} variant="outline" className="w-full">
                        <Sparkles />
                        Build with AI
                        {!aiAssistedEnabled && <span className="ml-1 text-xs">(Disabled)</span>}
                    </Button>

                    <Button onClick={onManualCreate} variant="ghost" className="w-full">
                        <Plus />
                        Create Manually
                    </Button>
                </div>
            </div>
        </GridCard>
    );
};
