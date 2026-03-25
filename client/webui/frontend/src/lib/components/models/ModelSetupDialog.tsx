import { Bot } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui";

interface ModelSetupDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    hasWritePermissions: boolean;
}

export function ModelSetupDialog({ open, onOpenChange, hasWritePermissions }: ModelSetupDialogProps) {
    const navigate = useNavigate();

    const handleAddModel = () => {
        navigate("/agents?tab=models");
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{hasWritePermissions ? "Set Up Your Default LLM Models" : "No Default LLM Models Available"}</DialogTitle>
                    <DialogDescription className="space-y-3 flex flex-col">
                        {hasWritePermissions ? (
                            <>
                                <span>
                                    Setting up your default General and Planning models unlocks powerful AI-enabled features like chatting with AI, agent creation and other helpful AI
                                    capabilities. Some features may not work as intended without a configured model.
                                </span>
                                <span className="flex items-center gap-1.5 inline">
                                    Add a model now to get the best experience, or explore first and set up models later from the
                                    <Bot className="inline size-4 shrink-0 mx-1" />
                                    <strong>Agent Mesh</strong> area.
                                </span>
                            </>
                        ) : (
                            <>
                                <span>
                                    This platform offers powerful AI-enabled features like chatting with AI, agent creation and other helpful AI capabilities. Some features may not work
                                    as intended without configured models.
                                </span>
                                <span>
                                    <strong>Contact an administrator</strong> to set up models for your agent mesh, or continue exploring the available features.
                                </span>
                            </>
                        )}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    {hasWritePermissions ? (
                        <>
                            <Button variant="ghost" onClick={() => onOpenChange(false)}>
                                Skip for Now
                            </Button>
                            <Button onClick={handleAddModel}>Add Model</Button>
                        </>
                    ) : (
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            Close
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
