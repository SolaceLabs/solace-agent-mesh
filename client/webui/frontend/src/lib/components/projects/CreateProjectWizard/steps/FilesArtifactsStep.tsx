import React, { useState, useRef, useCallback } from "react";
import { Upload, X, FileText, Trash2 } from "lucide-react";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Textarea } from "@/lib/components/ui";
import type { ProjectFormData } from "@/lib/types/projects";

interface FilesArtifactsStepProps {
    data: ProjectFormData;
    onDataChange: (data: Partial<ProjectFormData>) => void;
    onNext: () => void;
    onPrevious: () => void;
    onCancel: () => void;
    isValid: boolean;
    isSubmitting: boolean;
}

export const FilesArtifactsStep: React.FC<FilesArtifactsStepProps> = ({
    data,
    onDataChange,
    onNext,
    onPrevious,
    onCancel,
    isValid,
    isSubmitting,
}) => {
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const fileList = data.files;
    const fileDescriptions = data.fileDescriptions || {};

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);

            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                onDataChange({ files });
            }
        },
        [onDataChange]
    );

    const handleFileSelect = useCallback(
        (files: FileList | null) => {
            if (files) {
                onDataChange({ files });
            }
        },
        [onDataChange]
    );

    const handleRemoveFile = useCallback(
        (indexToRemove: number) => {
            if (!fileList) return;

            const fileToRemove = fileList[indexToRemove];
            const newFiles = Array.from(fileList).filter((_, index) => index !== indexToRemove);
            const dataTransfer = new DataTransfer();
            newFiles.forEach((file) => dataTransfer.items.add(file));

            const newFileList = dataTransfer.files.length > 0 ? dataTransfer.files : null;

            // Remove description for deleted file
            const newDescriptions = { ...fileDescriptions };
            if (fileToRemove.name in newDescriptions) {
                delete newDescriptions[fileToRemove.name];
            }

            onDataChange({
                files: newFileList,
                fileDescriptions: newDescriptions,
            });
        },
        [fileList, fileDescriptions, onDataChange]
    );

    const handleFileDescriptionChange = useCallback(
        (fileName: string, description: string) => {
            onDataChange({
                fileDescriptions: {
                    ...fileDescriptions,
                    [fileName]: description,
                },
            });
        },
        [fileDescriptions, onDataChange]
    );

    const openFileDialog = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const handleClearAllFiles = useCallback(() => {
        onDataChange({
            files: null,
            fileDescriptions: {},
        });
    }, [onDataChange]);

    return (
        <div className="space-y-6">
            <div className="text-center">
                <h2 className="text-2xl font-semibold text-foreground">Files & Artifacts</h2>
                <p className="text-muted-foreground mt-2">Upload project files, documents, or reference materials (optional)</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Upload Files</CardTitle>
                    <CardDescription>Add any files that are relevant to your project. These will be available to the AI agent.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-6">
                        {/* Hidden file input */}
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            className="hidden"
                            disabled={isSubmitting}
                            onChange={(e) => handleFileSelect(e.target.files)}
                        />

                        {/* Drag and drop area */}
                        <div
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={openFileDialog}
                            className={`
                                relative cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors
                                ${
                                    isDragOver
                                        ? "border-primary bg-primary/5"
                                        : "border-muted-foreground/25 hover:border-muted-foreground/50"
                                }
                                ${isSubmitting ? "cursor-not-allowed opacity-50" : ""}
                            `}
                        >
                            <div className="flex flex-col items-center gap-4">
                                <div className={`rounded-full p-4 ${isDragOver ? "bg-primary/10" : "bg-muted/20"}`}>
                                    <Upload className={`h-8 w-8 ${isDragOver ? "text-primary" : "text-muted-foreground"}`} />
                                </div>
                                <div className="space-y-2">
                                    <p className="text-lg font-medium text-foreground">
                                        {isDragOver ? "Drop files here" : "Choose files or drag and drop"}
                                    </p>
                                    <p className="text-sm text-muted-foreground">
                                        Upload project artifacts, documents, code files, or any reference materials
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        Supports all file types • No size limit per file
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* File list */}
                        {fileList && fileList.length > 0 && (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-lg font-medium text-foreground">Selected Files ({fileList.length})</h4>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={handleClearAllFiles}
                                        disabled={isSubmitting}
                                        className="text-destructive hover:text-destructive"
                                    >
                                        <Trash2 className="h-4 w-4 mr-2" />
                                        Clear All
                                    </Button>
                                </div>

                                <div className="space-y-1 max-h-96 overflow-y-auto pr-2">
                                    {Array.from(fileList).map((file, index) => (
                                        <Card key={index} className="bg-muted/20 py-2">
                                            <CardContent>
                                                <div className="space-y-0.5">
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-3 min-w-0 flex-1">
                                                            <div className="flex-shrink-0">
                                                                <FileText className="h-4 w-4 text-muted-foreground" />
                                                            </div>
                                                            <div className="min-w-0 flex-1">
                                                                <p className="text-sm font-medium text-foreground truncate" title={file.name}>
                                                                    {file.name}
                                                                </p>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {(file.size / 1024).toFixed(1)} KB • {file.type || "Unknown type"}
                                                                </p>
                                                            </div>
                                                        </div>
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => handleRemoveFile(index)}
                                                            disabled={isSubmitting}
                                                            className="text-muted-foreground hover:text-destructive"
                                                        >
                                                            <X className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                    <Textarea
                                                        placeholder={`Add a description for ${file.name} (optional)`}
                                                        className="bg-background text-foreground placeholder:text-muted-foreground"
                                                        rows={2}
                                                        disabled={isSubmitting}
                                                        value={fileDescriptions[file.name] || ""}
                                                        onChange={(e) => handleFileDescriptionChange(file.name, e.target.value)}
                                                    />
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <div className="flex justify-between pt-6">
                <Button variant="outline" onClick={onPrevious} disabled={isSubmitting}>
                    Previous
                </Button>
                <div className="flex gap-2">
                    <Button variant="ghost" onClick={onNext} disabled={isSubmitting}>
                        Skip Files
                    </Button>
                    <Button onClick={onNext} disabled={isSubmitting}>
                        Next: Review & Create
                    </Button>
                </div>
            </div>
        </div>
    );
};
