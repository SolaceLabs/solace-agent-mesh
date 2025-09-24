import React from "react";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Form, FormControl, FormField, FormItem, FormLabel, FormMessage, Input, Textarea } from "@/lib/components/ui";
import { useForm } from "react-hook-form";
import type { ProjectFormData } from "@/lib/types/projects";

interface ProjectDetailsStepProps {
    data: ProjectFormData;
    onDataChange: (data: Partial<ProjectFormData>) => void;
    onNext: () => void;
    onCancel: () => void;
    isValid: boolean;
    isSubmitting: boolean;
}

export const ProjectDetailsStep: React.FC<ProjectDetailsStepProps> = ({
    data,
    onDataChange,
    onNext,
    onCancel,
    isValid,
    isSubmitting,
}) => {
    const form = useForm<Pick<ProjectFormData, "name" | "description" | "system_prompt">>({
        defaultValues: {
            name: data.name || "",
            description: data.description || "",
            system_prompt: data.system_prompt || "",
        },
        mode: "onChange",
    });

    // Update parent state when form values change
    React.useEffect(() => {
        const subscription = form.watch((values) => {
            onDataChange({
                name: values.name || "",
                description: values.description || "",
                system_prompt: values.system_prompt || "",
            });
        });
        return () => subscription.unsubscribe();
    }, [form, onDataChange]);

    const handleNext = () => {
        if (isValid) {
            onNext();
        }
    };

    return (
        <div className="space-y-6">
            <div className="text-center">
                <h2 className="text-2xl font-semibold text-foreground">Project Details</h2>
                <p className="text-muted-foreground mt-2">Let's start with the basic information about your project</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Basic Information</CardTitle>
                    <CardDescription>Provide the essential details for your project</CardDescription>
                </CardHeader>
                <CardContent>
                    <Form {...form}>
                        <div className="space-y-6">
                            <FormField
                                control={form.control}
                                name="name"
                                rules={{
                                    required: "Project name is required",
                                    minLength: {
                                        value: 1,
                                        message: "Project name must be at least 1 character",
                                    },
                                    maxLength: {
                                        value: 255,
                                        message: "Project name must be less than 255 characters",
                                    },
                                }}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel className="text-foreground">Project Name *</FormLabel>
                                        <FormControl>
                                            <Input
                                                placeholder="Enter a descriptive name for your project..."
                                                className="bg-background border text-foreground placeholder:text-muted-foreground"
                                                disabled={isSubmitting}
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
                                        message: "Description must be less than 1000 characters",
                                    },
                                }}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel className="text-foreground">Description</FormLabel>
                                        <FormControl>
                                            <Textarea
                                                placeholder="Describe what this project is about, its goals, or any relevant context..."
                                                className="bg-background border text-foreground placeholder:text-muted-foreground min-h-[100px]"
                                                disabled={isSubmitting}
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
                                        message: "System prompt must be less than 4000 characters",
                                    },
                                }}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel className="text-foreground">System Prompt</FormLabel>
                                        <FormControl>
                                            <Textarea
                                                placeholder="Provide instructions or context that will guide the AI agent when working on this project..."
                                                className="bg-background border text-foreground placeholder:text-muted-foreground min-h-[120px]"
                                                disabled={isSubmitting}
                                                {...field}
                                            />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                        </div>
                    </Form>
                </CardContent>
            </Card>

            <div className="flex justify-between pt-6">
                <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
                    Cancel
                </Button>
                <Button onClick={handleNext} disabled={!isValid || isSubmitting}>
                    Next: Files & Artifacts
                </Button>
            </div>
        </div>
    );
};
