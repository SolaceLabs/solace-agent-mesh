import React from "react";
import { Loader2, FileText, AlertTriangle } from "lucide-react";

import { useProjectArtifacts } from "@/lib/hooks/useProjectArtifacts";
import type { Project } from "@/lib/types/projects";
import { ArtifactCard } from "../chat/artifact/ArtifactCard";

interface ProjectFilesManagerProps {
    project: Project;
}

export const ProjectFilesManager: React.FC<ProjectFilesManagerProps> = ({ project }) => {
    const { artifacts, isLoading, error } = useProjectArtifacts(project.id);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-6">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                <AlertTriangle className="h-4 w-4" />
                <span>Error loading files: {error}</span>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            <h4 className="font-semibold text-foreground">Project Files</h4>
            {artifacts.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-md border border-dashed p-8 text-center text-muted-foreground">
                    <FileText className="mb-2 h-8 w-8" />
                    <p>No files have been added to this project yet.</p>
                </div>
            ) : (
                <div className="overflow-hidden rounded-md border">
                    {artifacts.map(artifact => (
                        <ArtifactCard key={artifact.filename} artifact={artifact} />
                    ))}
                </div>
            )}
        </div>
    );
};
