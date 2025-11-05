import React from "react";
import { Plus, Sparkles } from "lucide-react";
import { useConfigContext } from "@/lib/hooks";
import { Button } from "@/lib/components/ui";

interface CreatePromptCardProps {
    onManualCreate: () => void;
    onAIAssisted: () => void;
}

export const CreatePromptCard: React.FC<CreatePromptCardProps> = ({ onManualCreate, onAIAssisted }) => {
    const { configFeatureEnablement } = useConfigContext();
    const aiAssistedEnabled = configFeatureEnablement?.promptAIAssisted ?? true;
    return (
        <div className="bg-card h-[280px] w-full flex-shrink-0 rounded-lg sm:w-[380px] border-2 border-dashed border-primary/30">
            <div className="flex h-full w-full flex-col items-center justify-center p-8 gap-6">
                <h3 className="text-lg font-semibold text-center">Create New Prompt</h3>

                <div className="flex flex-col gap-3 w-full max-w-[240px]">
                    <Button
                        onClick={onAIAssisted}
                        disabled={!aiAssistedEnabled}
                        variant="outline"
                        className="w-full"
                    >
                        <Sparkles className="h-4 w-4 mr-2" />
                        Build with AI
                        {!aiAssistedEnabled && <span className="text-xs ml-1">(Disabled)</span>}
                    </Button>

                    <Button
                        onClick={onManualCreate}
                        variant="ghost"
                        className="w-full"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        Create Manually
                    </Button>
                </div>
            </div>
        </div>
    );
};