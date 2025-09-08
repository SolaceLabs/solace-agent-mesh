import React from "react";
import { ArrowLeft, CheckCircle } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/lib/components/ui/card";
import type { Project } from "@/lib/types/projects";

interface ProjectDetailViewProps {
    project: Project;
    isActive: boolean;
    onBack: () => void;
    onActivate: (project: Project) => void;
}

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({ project, isActive, onBack, onActivate }) => {
    return (
        <div className="space-y-6">
            <Button variant="ghost" onClick={onBack} className="flex items-center gap-2 text-muted-foreground">
                <ArrowLeft className="h-4 w-4" />
                Back to all projects
            </Button>

            <Card className="bg-card">
                <CardHeader>
                    <CardTitle className="text-2xl">{project.name}</CardTitle>
                    <CardDescription>{project.description || "No description provided."}</CardDescription>
                </CardHeader>
                <CardContent>
                    {project.system_prompt && (
                        <div className="mb-6 space-y-2">
                            <h4 className="font-semibold text-foreground">System Prompt</h4>
                            <p className="whitespace-pre-wrap rounded-md bg-muted p-4 text-sm text-muted-foreground">
                                {project.system_prompt}
                            </p>
                        </div>
                    )}
                    <div className="flex justify-start">
                        {isActive ? (
                            <Button variant="outline" disabled className="flex items-center gap-2">
                                <CheckCircle className="h-4 w-4 text-green-500" />
                                Active
                            </Button>
                        ) : (
                            <Button onClick={() => onActivate(project)}>Activate Project</Button>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};
