import React from "react";
import { Plus, Sparkles } from "lucide-react";
import { useConfigContext } from "@/lib/hooks";
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
            <div className="w-full max-w-[960px] p-12">
                <div className="flex h-full w-full flex-col items-center justify-center gap-8">
                    {/* Large circular plus icon */}
                    <div className="flex items-center justify-center w-32 h-32 rounded-full bg-muted/50">
                        <Plus className="h-12 w-12 text-primary" strokeWidth={2} />
                    </div>
                    
                    {/* Title and description */}
                    <div className="flex flex-col items-center gap-3">
                        <h2 className="text-3xl font-semibold text-foreground">Create New Prompt</h2>
                        <p className="text-base text-muted-foreground">Choose how you'd like to create your prompt</p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-col gap-4 w-full max-w-[400px]">
                        <Button
                            onClick={onAIAssisted}
                            disabled={!aiAssistedEnabled}
                            variant="default"
                            size="lg"
                            className="w-full h-14 text-base"
                        >
                            <Sparkles className="h-5 w-5 mr-2" />
                            Build with AI
                            {!aiAssistedEnabled && <span className="text-xs ml-1">(Disabled)</span>}
                        </Button>

                        <Button
                            onClick={onManualCreate}
                            variant="outline"
                            size="lg"
                            className="w-full h-14 text-base"
                        >
                            <Plus className="h-5 w-5 mr-2" />
                            Create Manually
                        </Button>
                    </div>
                </div>
            </div>
        );
    }
    
    // Original compact version for grid display
    return (
        <div className="bg-card h-[200px] w-full flex-shrink-0 rounded-lg sm:w-[380px] border-2 border-dashed border-primary/30">
            <div className="flex h-full w-full flex-col items-center justify-center p-6 gap-4">
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