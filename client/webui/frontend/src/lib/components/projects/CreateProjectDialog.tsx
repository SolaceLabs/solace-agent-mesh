import React, { useState, useRef, useCallback } from "react";
import { useForm } from "react-hook-form";
import { Upload, X, FileText } from "lucide-react";

import {
    Button,
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
    Input,
    Textarea,
} from "@/lib/components/ui";
import type { ProjectFormData } from "@/lib/types/projects";

interface CreateProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: ProjectFormData) => Promise<void>;
    isLoading?: boolean;
}

export const CreateProjectDialog: React.FC<CreateProjectDialogProps> = ({
    isOpen,
    onClose,
    onSubmit,
    isLoading = false,
}) => {
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const form = useForm<ProjectFormData>({
        defaultValues: {
            name: "",
            description: "",
            system_prompt: "",
            files: null,
        },
    });

    const fileList = form.watch("files");

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

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
        
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            form.setValue("files", files);
        }
    }, [form]);

    const handleFileSelect = useCallback((files: FileList | null) => {
        if (files) {
            form.setValue("files", files);
        }
    }, [form]);

    const handleRemoveFile = useCallback((indexToRemove: number) => {
        if (!fileList) return;
        
        const newFiles = Array.from(fileList).filter((_, index) => index !== indexToRemove);
        const dataTransfer = new DataTransfer();
        newFiles.forEach(file => dataTransfer.items.add(file));
        form.setValue("files", dataTransfer.files.length > 0 ? dataTransfer.files : null);
    }, [fileList, form]);

    const openFileDialog = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const handleSubmit = async (data: ProjectFormData) => {
        if (isSubmitting || isLoading) return;
        
        setIsSubmitting(true);
        try {
            await onSubmit(data);
            form.reset();
            onClose();
        } catch (error) {
            console.error("Error creating project:", error);
            // Error handling is managed by the parent component
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleClose = () => {
        if (isSubmitting) return;
        form.reset();
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[425px] max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle className="text-foreground">Create New Project</DialogTitle>
                    <DialogDescription className="text-muted-foreground">
                        Create a new project to organize your chats and sessions.
                    </DialogDescription>
                </DialogHeader>
                
                <Form {...form}>
                    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4 flex-1 overflow-hidden flex flex-col">
                        <div className="space-y-4 overflow-y-auto flex-1 pr-2">
                        <FormField
                            control={form.control}
                            name="name"
                            rules={{
                                required: "Project name is required",
                                minLength: {
                                    value: 1,
                                    message: "Project name must be at least 1 character"
                                },
                                maxLength: {
                                    value: 255,
                                    message: "Project name must be less than 255 characters"
                                }
                            }}
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="text-foreground">Project Name</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="Enter project name..."
                                            className="bg-background border text-foreground placeholder:text-muted-foreground"
                                            disabled={isSubmitting || isLoading}
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        
                        <FormField
                            control={form.control}
                            name="description"
                            rules={{
                                maxLength: {
                                    value: 1000,
                                    message: "Description must be less than 1000 characters"
                                }
                            }}
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="text-foreground">Description (Optional)</FormLabel>
                                    <FormControl>
                                        <Textarea
                                            placeholder="Enter project description..."
                                            className="bg-background border text-foreground placeholder:text-muted-foreground min-h-[80px]"
                                            disabled={isSubmitting || isLoading}
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />
                        
                        <FormField
                            control={form.control}
                            name="system_prompt"
                            rules={{
                                maxLength: {
                                    value: 4000,
                                    message: "System prompt must be less than 4000 characters"
                                }
                            }}
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="text-foreground">System Prompt (Optional)</FormLabel>
                                    <FormControl>
                                        <Textarea
                                            placeholder="Enter a system prompt to guide the agent..."
                                            className="bg-background border text-foreground placeholder:text-muted-foreground min-h-[120px]"
                                            disabled={isSubmitting || isLoading}
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="files"
                            render={({ field: { onChange, value, ...rest } }) => (
                                <FormItem>
                                    <FormLabel className="text-foreground">Artifacts (Optional)</FormLabel>
                                    <FormControl>
                                        <div className="space-y-3">
                                            {/* Hidden file input */}
                                            <input
                                                ref={fileInputRef}
                                                type="file"
                                                multiple
                                                className="hidden"
                                                disabled={isSubmitting || isLoading}
                                                onChange={(e) => {
                                                    handleFileSelect(e.target.files);
                                                }}
                                            />
                                            
                                            {/* Custom drag and drop area */}
                                            <div
                                                onDragOver={handleDragOver}
                                                onDragLeave={handleDragLeave}
                                                onDrop={handleDrop}
                                                onClick={openFileDialog}
                                                className={`
                                                    relative cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors
                                                    ${isDragOver
                                                        ? 'border-primary bg-primary/5'
                                                        : 'border-muted-foreground/25 hover:border-muted-foreground/50'
                                                    }
                                                    ${isSubmitting || isLoading ? 'cursor-not-allowed opacity-50' : ''}
                                                `}
                                            >
                                                <div className="flex flex-col items-center gap-2">
                                                    <div className={`rounded-full p-3 ${isDragOver ? 'bg-primary/10' : 'bg-muted/20'}`}>
                                                        <Upload className={`h-6 w-6 ${isDragOver ? 'text-primary' : 'text-muted-foreground'}`} />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <p className="text-sm font-medium text-foreground">
                                                            {isDragOver ? 'Drop files here' : 'Choose files or drag and drop'}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">
                                                            Upload project artifacts, documents, or reference files
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        {fileList && fileList.length > 0 && (
                            <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-sm font-medium text-foreground">
                                        Selected Files ({fileList.length})
                                    </h4>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => form.setValue("files", null)}
                                        className="h-auto p-1 text-muted-foreground hover:text-foreground"
                                        disabled={isSubmitting || isLoading}
                                    >
                                        <X className="h-4 w-4" />
                                    </Button>
                                </div>
                                <div className="space-y-2 max-h-32 overflow-y-auto pr-2">
                                    {Array.from(fileList).map((file, index) => (
                                        <div
                                            key={index}
                                            className="flex items-center justify-between rounded-md border bg-background p-3"
                                        >
                                            <div className="flex items-center gap-3 min-w-0 flex-1">
                                                <div className="flex-shrink-0">
                                                    <FileText className="h-4 w-4 text-muted-foreground" />
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium text-foreground truncate">
                                                        {file.name}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {(file.size / 1024).toFixed(1)} KB
                                                    </p>
                                                </div>
                                            </div>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => handleRemoveFile(index)}
                                                className="h-auto p-1 text-muted-foreground hover:text-destructive"
                                                disabled={isSubmitting || isLoading}
                                            >
                                                <X className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        </div>

                        <div className="flex justify-end gap-2 pt-4 border-t bg-background mt-4">
                            <Button
                                variant="outline"
                                onClick={handleClose}
                                disabled={isSubmitting || isLoading}
                                type="button"
                            >
                                Cancel
                            </Button>
                            <Button variant="default" type="submit" disabled={isSubmitting || isLoading}>
                                {isSubmitting ? "Creating..." : "Create Project"}
                            </Button>
                        </div>
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
};
