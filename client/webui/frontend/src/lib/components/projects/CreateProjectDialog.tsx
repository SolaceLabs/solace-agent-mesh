import React, { useState } from "react";
import { useForm } from "react-hook-form";

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
    Textarea
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
    isLoading = false 
}) => {
    const [isSubmitting, setIsSubmitting] = useState(false);
    
    const form = useForm<ProjectFormData>({
        defaultValues: {
            name: "",
            description: "",
            system_prompt: "",
        },
    });

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
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle className="text-foreground">Create New Project</DialogTitle>
                    <DialogDescription className="text-muted-foreground">
                        Create a new project to organize your chats and sessions.
                    </DialogDescription>
                </DialogHeader>
                
                <Form {...form}>
                    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
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
                        
                        <div className="flex justify-end gap-2 pt-4">
                            <Button 
                                variant="outline" 
                                onClick={handleClose}
                                disabled={isSubmitting || isLoading}
                                type="button"
                            >
                                Cancel
                            </Button>
                            <Button 
                                variant="default" 
                                type="submit"
                                disabled={isSubmitting || isLoading}
                            >
                                {isSubmitting ? "Creating..." : "Create Project"}
                            </Button>
                        </div>
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
};
