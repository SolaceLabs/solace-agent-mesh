import React, { useState, useEffect } from "react";
import { ArrowLeft, CheckCircle, Edit } from "lucide-react";

import { Button, Input, Textarea } from "@/lib/components/ui";
import { Card, CardContent, CardHeader, CardTitle } from "@/lib/components/ui/card";
import { useProjectContext } from "@/lib/providers";
import type { Project, UpdateProjectData } from "@/lib/types/projects";
import { ProjectFilesManager } from ".";

interface ProjectDetailViewProps {
    project: Project;
    isActive: boolean;
    onBack: () => void;
    onActivate: (project: Project) => void;
}

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({ project, isActive, onBack, onActivate }) => {
    const { updateProject } = useProjectContext();
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // Form state
    const [name, setName] = useState(project.name);
    const [description, setDescription] = useState(project.description || "");
    const [systemPrompt, setSystemPrompt] = useState(project.systemPrompt || "");

    useEffect(() => {
        // Reset form state if the project prop changes (e.g. after save)
        setName(project.name);
        setDescription(project.description || "");
        setSystemPrompt(project.systemPrompt || "");
    }, [project]);

    const handleEditToggle = () => {
        if (isEditing) {
            // Cancel editing
            setName(project.name);
            setDescription(project.description || "");
            setSystemPrompt(project.systemPrompt || "");
        }
        setIsEditing(!isEditing);
    };

    const handleSave = async () => {
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
        } catch (error) {
            console.error("Failed to save project changes:", error);
            // Optionally show a notification to the user here
        } finally {
            setIsSaving(false);
        }
    };

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
                        <h4 className="font-semibold text-foreground">System Prompt</h4>
                        {isEditing ? (
                            <Textarea value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)} placeholder="No system prompt provided." rows={5} />
                        ) : (
                            <p className="whitespace-pre-wrap rounded-md bg-muted p-4 text-sm text-muted-foreground min-h-[40px]">{project.systemPrompt || <span className="italic">No system prompt provided.</span>}</p>
                        )}
                    </div>

                    <div className="mb-6">
                        <ProjectFilesManager project={project} isEditing={isEditing} />
                    </div>

                    <div className="flex justify-start gap-2">
                        {isEditing ? (
                            <>
                                <Button onClick={handleSave} disabled={isSaving}>
                                    {isSaving ? "Saving..." : "Save Changes"}
                                </Button>
                                <Button variant="outline" onClick={handleEditToggle} disabled={isSaving}>
                                    Cancel
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button variant="outline" onClick={handleEditToggle} className="flex items-center gap-2">
                                    <Edit className="h-4 w-4" />
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
