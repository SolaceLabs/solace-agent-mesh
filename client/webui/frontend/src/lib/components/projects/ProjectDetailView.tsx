import React, { useState, useEffect } from "react";
import { ArrowLeft, CheckCircle, Pencil, AlertCircle } from "lucide-react";

import { Button, Input, Textarea } from "@/lib/components/ui";
import { Card, CardContent, CardHeader, CardTitle } from "@/lib/components/ui/card";
import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { ProjectFilesManager } from ".";
import { useConfigContext } from "@/lib/hooks";

interface ProjectDetailViewProps {
    project: Project;
    isActive: boolean;
    onBack: () => void;
    onActivate: (project: Project) => void;
}

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({ project, isActive, onBack, onActivate }) => {
    const { updateProject } = useProjectContext();
    const { validationLimits } = useConfigContext();
    const MAX_INSTRUCTIONS_LENGTH = validationLimits?.projectInstructionsMax ?? 4000;
    
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [name, setName] = useState(project.name);
    const [description, setDescription] = useState(project.description || "");
    const [systemPrompt, setSystemPrompt] = useState(project.systemPrompt || "");

    useEffect(() => {
        // Reset form state if the project prop changes (e.g. after save)
        setName(project.name);
        setDescription(project.description || "");
        setSystemPrompt(project.systemPrompt || "");
        setError(null);
    }, [project]);

    const handleEditToggle = () => {
        if (isEditing) {
            // Cancel editing
            setName(project.name);
            setDescription(project.description || "");
            setSystemPrompt(project.systemPrompt || "");
            setError(null);
        }
        setIsEditing(!isEditing);
    };

    const handleSave = async () => {
        setError(null);

        const updateData: UpdateProjectData = {};
        if (name.trim() !== project.name) updateData.name = name.trim();
        if (description.trim() !== (project.description || "")) updateData.description = description.trim();
        if (systemPrompt.trim() !== (project.systemPrompt || "")) updateData.systemPrompt = systemPrompt.trim();

        if (Object.keys(updateData).length === 0) {
            setIsEditing(false);
            return;
        }

        setIsSaving(true);
        try {
            await updateProject(project.id, updateData);
            setIsEditing(false);
            setError(null);
        } catch (error) {
            console.error("Failed to save project changes:", error);
            const errorMessage = error instanceof Error ? error.message : "Failed to save project changes";
            setError(errorMessage);
        } finally {
            setIsSaving(false);
        }
    };

    const characterCount = systemPrompt.length;
    const isOverLimit = characterCount > MAX_INSTRUCTIONS_LENGTH;
    const isNearLimit = characterCount > MAX_INSTRUCTIONS_LENGTH * 0.9;

    return (
        <div className="space-y-6">
            <Button variant="ghost" onClick={onBack} className="flex items-center gap-2 text-muted-foreground">
                <ArrowLeft className="h-4 w-4" />
                Back to all projects
            </Button>

            <Card className="bg-card">
                <CardHeader>
                    {isEditing ? (
                        <div className="space-y-2">
                            <h4 className="font-semibold text-foreground">Project Name</h4>
                            <Input id="projectName" value={name} onChange={e => setName(e.target.value)} />
                        </div>
                    ) : (
                        <CardTitle className="text-2xl">{project.name}</CardTitle>
                    )}
                </CardHeader>
                <CardContent>
                    <div className="mb-6 space-y-2">
                        <h4 className="font-semibold text-foreground">Description</h4>
                        {isEditing ? <Textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="No description provided." /> : <p className="text-sm text-muted-foreground min-h-[20px]">{project.description || <span className="italic">No description provided.</span>}</p>}
                    </div>

                    <div className="mb-6 space-y-2">
                        <h4 className="font-semibold text-foreground">Instructions</h4>
                        {isEditing ? (
                            <div className="space-y-2">
                                <div className="relative">
                                    <Textarea
                                        value={systemPrompt}
                                        onChange={e => setSystemPrompt(e.target.value)}
                                        placeholder="No instructions provided."
                                        rows={5}
                                        className={isOverLimit ? 'border-destructive focus-visible:ring-destructive' : ''}
                                    />
                                    <div className={`mt-1 text-xs ${isOverLimit ? 'text-destructive font-medium' : isNearLimit ? 'text-orange-500' : 'text-muted-foreground'}`}>
                                        {isOverLimit
                                            ? `Instructions must be less than ${MAX_INSTRUCTIONS_LENGTH} characters (currently ${characterCount})`
                                            : `${characterCount} / ${MAX_INSTRUCTIONS_LENGTH} characters`
                                        }
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <p className="whitespace-pre-wrap rounded-md bg-muted p-4 text-sm text-muted-foreground min-h-[40px]">{project.systemPrompt || <span className="italic">No instructions provided.</span>}</p>
                        )}
                    </div>

                    {error && (
                        <div className="mb-6 flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                            <AlertCircle className="h-4 w-4 flex-shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    <div className="mb-6">
                        <ProjectFilesManager project={project} isEditing={isEditing} />
                    </div>

                    <div className="flex justify-start gap-2">
                        {isEditing ? (
                            <>
                                <Button onClick={handleSave} disabled={isSaving || isOverLimit}>
                                    {isSaving ? "Saving..." : "Save Changes"}
                                </Button>
                                <Button variant="outline" onClick={handleEditToggle} disabled={isSaving}>
                                    Cancel
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button variant="outline" onClick={handleEditToggle} className="flex items-center gap-2">
                                    <Pencil className="h-4 w-4 mr-2" />
                                    Edit Project
                                </Button>

                                {isActive ? (
                                    <Button variant="outline" disabled className="flex items-center gap-2">
                                        <CheckCircle className="h-4 w-4 text-green-500" />
                                        Active
                                    </Button>
                                ) : (
                                    <Button onClick={() => onActivate(project)}>Activate Project</Button>
                                )}
                            </>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};
