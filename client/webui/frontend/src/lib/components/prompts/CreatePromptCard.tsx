import React from "react";
import { Plus, Sparkles, Pencil } from "lucide-react";
import { useConfigContext } from "@/lib/hooks";

interface CreatePromptCardProps {
    onManualCreate: () => void;
    onAIAssisted: () => void;
}

export const CreatePromptCard: React.FC<CreatePromptCardProps> = ({ onManualCreate, onAIAssisted }) => {
    const { configFeatureEnablement } = useConfigContext();
    const aiAssistedEnabled = configFeatureEnablement?.promptAIAssisted ?? true;
    return (
        <div className="bg-card h-[400px] w-full flex-shrink-0 rounded-lg sm:w-[380px] border-2 border-dashed border-primary/30 hover:border-primary/60 transition-colors">
            <div className="flex h-full w-full flex-col items-center justify-center p-6 gap-6">
                <div className="text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                        <Plus className="h-8 w-8 text-primary" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">Create New Prompt</h3>
                    <p className="text-sm text-muted-foreground">
                        Choose how you'd like to create your prompt
                    </p>
                </div>

                <div className="flex flex-col gap-3 w-full max-w-xs">
                    <button
                        onClick={onAIAssisted}
                        disabled={!aiAssistedEnabled}
                        className={`flex items-center justify-center gap-3 rounded-lg px-6 py-4 transition-colors shadow-md ${
                            aiAssistedEnabled
                                ? 'bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-lg'
                                : 'bg-muted text-muted-foreground cursor-not-allowed opacity-60'
                        }`}
                        title={aiAssistedEnabled ? undefined : "AI-Assisted Builder requires LLM configuration"}
                    >
                        <Sparkles className="h-5 w-5" />
                        <span className="font-medium">AI-Assisted Builder</span>
                        {!aiAssistedEnabled && <span className="text-xs">(Disabled)</span>}
                    </button>

                    <button
                        onClick={onManualCreate}
                        className={`flex items-center justify-center gap-3 rounded-lg px-6 py-4 transition-colors ${
                            aiAssistedEnabled
                                ? 'border-2 border-border bg-background hover:bg-muted'
                                : 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-md hover:shadow-lg'
                        }`}
                    >
                        <Pencil className="h-5 w-5" />
                        <span className="font-medium">Manual Creation</span>
                    </button>
                </div>

                <div className="text-xs text-muted-foreground text-center max-w-xs">
                    {aiAssistedEnabled
                        ? 'AI-Assisted helps you build prompts through conversation, while Manual gives you direct control'
                        : 'AI-Assisted Builder requires LLM configuration. Use Manual Creation to build prompts.'}
                </div>
            </div>
        </div>
    );
};