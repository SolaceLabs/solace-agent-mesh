import React, { useState, useEffect } from "react";
import { Bot, Pencil } from "lucide-react";

import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui";
import { useAgentCards } from "@/lib/hooks";
import type { Project } from "@/lib/types/projects";

interface DefaultAgentSectionProps {
    project: Project;
    onSave: (defaultAgentId: string | null) => Promise<void>;
    isSaving: boolean;
}

export const DefaultAgentSection: React.FC<DefaultAgentSectionProps> = ({
    project,
    onSave,
    isSaving,
}) => {
    const [isEditing, setIsEditing] = useState(false);
    const [selectedAgentId, setSelectedAgentId] = useState<string | null>(project.defaultAgentId || null);
    const { agents, isLoading: agentsLoading } = useAgentCards();

    useEffect(() => {
        setSelectedAgentId(project.defaultAgentId || null);
    }, [project.defaultAgentId]);

    const handleSave = async () => {
        if (selectedAgentId !== (project.defaultAgentId || null)) {
            await onSave(selectedAgentId);
        }
        setIsEditing(false);
    };

    const handleCancel = () => {
        setSelectedAgentId(project.defaultAgentId || null);
        setIsEditing(false);
    };

    const currentAgent = agents.find(agent => agent.name === project.defaultAgentId);
    const displayName = currentAgent?.displayName || project.defaultAgentId || "None";

    return (
        <>
            <div className="mb-6">
                <div className="flex items-center justify-between px-4 mb-3">
                    <h3 className="text-sm font-semibold text-foreground">Default Agent</h3>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsEditing(true)}
                        disabled={agentsLoading}
                        className="h-8 w-8 p-0"
                        tooltip="Edit"
                    >
                        <Pencil className="h-4 w-4" />
                    </Button>
                </div>

                <div className="px-4">
                    <div className="text-sm text-muted-foreground rounded-md bg-muted p-2.5 flex items-center">
                        {project.defaultAgentId ? (
                            <div className="flex items-center gap-2">
                                <Bot className="h-4 w-4" />
                                <span>{displayName}</span>
                            </div>
                        ) : (
                            <span className="w-full text-center">No default agent set.</span>
                        )}
                    </div>
                </div>
            </div>

            <Dialog open={isEditing} onOpenChange={setIsEditing}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Edit Default Agent</DialogTitle>
                        <DialogDescription>
                            Select the default agent for this project. This agent will be used when starting new chats in this project.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <Select
                            value={selectedAgentId || "none"}
                            onValueChange={(value) => setSelectedAgentId(value === "none" ? null : value)}
                            disabled={isSaving || agentsLoading}
                        >
                            <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select default agent..." />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">
                                    <span className="text-muted-foreground italic">No default agent</span>
                                </SelectItem>
                                {agents.map((agent) => (
                                    <SelectItem key={agent.name} value={agent.name || ""}>
                                        {agent.displayName || agent.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="ghost"
                            onClick={handleCancel}
                            disabled={isSaving}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleSave}
                            disabled={isSaving || agentsLoading}
                        >
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};