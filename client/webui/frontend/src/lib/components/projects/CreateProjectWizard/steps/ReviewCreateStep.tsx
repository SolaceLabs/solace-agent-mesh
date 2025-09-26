import React from "react";
import { Edit, FileText, MessageSquare, User } from "lucide-react";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/lib/components/ui";
import type { ProjectFormData } from "@/lib/types/projects";

interface ReviewCreateStepProps {
    data: ProjectFormData;
    onDataChange: (data: Partial<ProjectFormData>) => void;
    onPrevious: () => void;
    onCancel: () => void;
    onSubmit: () => Promise<void>;
    goToStep: (step: number) => void;
    isValid: boolean;
    isSubmitting: boolean;
}

export const ReviewCreateStep: React.FC<ReviewCreateStepProps> = ({
    data,
    onPrevious,
    onCancel,
    onSubmit,
    goToStep,
    isValid,
    isSubmitting,
}) => {
    const fileCount = data.files ? data.files.length : 0;
    const totalFileSize = data.files ? Array.from(data.files).reduce((total, file) => total + file.size, 0) : 0;

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    };

    return (
        <div className="space-y-6">
            <div className="text-center">
                <h2 className="text-2xl font-semibold text-foreground">Review & Create</h2>
                <p className="text-muted-foreground mt-2">Review your project details and create your new project</p>
            </div>

            {/* Project Details Summary */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2">
                            <User className="h-5 w-5" />
                            Project Details
                        </CardTitle>
                        <Button variant="outline" size="sm" onClick={() => goToStep(1)} disabled={isSubmitting}>
                            <Edit className="h-4 w-4 mr-2" />
                            Edit
                        </Button>
                    </div>
                    <CardDescription>Basic information about your project</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div>
                            <h4 className="text-sm font-medium text-muted-foreground">Project Name</h4>
                            <p className="text-foreground font-medium">{data.name || "Untitled Project"}</p>
                        </div>
                        {data.description && (
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
                                <p className="text-foreground text-sm">{data.description}</p>
                            </div>
                        )}
                        {data.system_prompt && (
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground">System Prompt</h4>
                                <div className="bg-muted/20 rounded-md p-3 mt-1">
                                    <p className="text-foreground text-sm whitespace-pre-wrap">{data.system_prompt}</p>
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Files Summary */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2">
                            <FileText className="h-5 w-5" />
                            Files & Artifacts
                        </CardTitle>
                        <Button variant="outline" size="sm" onClick={() => goToStep(2)} disabled={isSubmitting}>
                            <Edit className="h-4 w-4 mr-2" />
                            Edit
                        </Button>
                    </div>
                    <CardDescription>
                        {fileCount > 0 ? `${fileCount} file${fileCount > 1 ? "s" : ""} selected` : "No files selected"}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {fileCount > 0 ? (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">Total files:</span>
                                <span className="font-medium">{fileCount}</span>
                            </div>
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">Total size:</span>
                                <span className="font-medium">{formatFileSize(totalFileSize)}</span>
                            </div>
                            <div className="space-y-2">
                                <h4 className="text-sm font-medium text-muted-foreground">Files:</h4>
                                <div className="space-y-2 max-h-32 overflow-y-auto">
                                    {Array.from(data.files!).map((file, index) => (
                                        <div key={index} className="flex items-center justify-between text-sm bg-muted/20 rounded p-2">
                                            <div className="flex items-center gap-2 min-w-0 flex-1">
                                                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                                                <span className="truncate font-medium" title={file.name}>
                                                    {file.name}
                                                </span>
                                            </div>
                                            <span className="text-muted-foreground text-xs">
                                                {formatFileSize(file.size)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center py-8 text-muted-foreground">
                            <div className="text-center">
                                <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p className="text-sm">No files selected</p>
                                <p className="text-xs">You can add files later if needed</p>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            <div className="flex justify-between pt-6">
                <Button variant="outline" onClick={onPrevious} disabled={isSubmitting}>
                    Previous
                </Button>
                <div className="flex gap-2">
                    <Button variant="ghost" onClick={onCancel} disabled={isSubmitting}>
                        Cancel
                    </Button>
                    <Button onClick={onSubmit} disabled={!isValid || isSubmitting}>
                        {isSubmitting ? "Creating Project..." : "Create Project"}
                    </Button>
                </div>
            </div>
        </div>
    );
};
