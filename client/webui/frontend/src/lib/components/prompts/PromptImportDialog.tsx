import React, { useState, useRef, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, CheckCircle, FileJson } from "lucide-react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Button, Input, Label } from "@/lib/components/ui";
import { Alert, AlertDescription } from "@/lib/components/ui/alert";
import { MessageBanner } from "@/lib/components";
import {
    promptImportSchema,
    promptImportCommandSchema,
    PROMPT_FIELD_LIMITS,
    formatZodErrors,
    hasPathError,
    getPathErrorMessage,
    detectTruncationWarnings,
    type PromptImportData,
    type PromptImportCommandForm,
    type TruncationWarning,
} from "@/lib/schemas";

interface PromptImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (data: PromptImportData, options: { preserveCommand: boolean; preserveCategory: boolean }) => Promise<void>;
}

export const PromptImportDialog: React.FC<PromptImportDialogProps> = ({ open, onOpenChange, onImport }) => {
    const [importData, setImportData] = useState<PromptImportData | null>(null);
    const [fileError, setFileError] = useState<string | null>(null);
    const [validationErrors, setValidationErrors] = useState<string[]>([]);
    const [truncationWarnings, setTruncationWarnings] = useState<TruncationWarning[]>([]);
    const [isImporting, setIsImporting] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFileName, setSelectedFileName] = useState<string>("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Form for the editable command field
    const {
        register,
        handleSubmit,
        formState: { errors },
        reset: resetForm,
        setValue,
    } = useForm<PromptImportCommandForm>({
        resolver: zodResolver(promptImportCommandSchema),
        defaultValues: {
            command: "",
        },
        mode: "onChange",
    });

    const validateAndParseFile = useCallback(async (file: File): Promise<PromptImportData | null> => {
        setFileError(null);
        setValidationErrors([]);
        setTruncationWarnings([]);
        setImportData(null);

        // Validate file type
        if (!file.name.endsWith(".json")) {
            setFileError("Please select a JSON file");
            return null;
        }

        // Validate file size (1MB limit)
        if (file.size > 1024 * 1024) {
            setFileError("File size must be less than 1MB");
            return null;
        }

        try {
            const text = await file.text();
            let data: unknown;

            try {
                data = JSON.parse(text);
            } catch {
                setFileError("Failed to parse JSON file. Please ensure it's a valid JSON format.");
                return null;
            }

            // Validate using zod schema
            const result = promptImportSchema.safeParse(data);

            if (!result.success) {
                // Extract and format validation errors using helper functions
                const errors = formatZodErrors(result.error);

                // Check if it's a version error
                if (hasPathError(result.error, "version")) {
                    const versionMessage = getPathErrorMessage(result.error, "version");
                    setFileError(versionMessage || "Invalid version format");
                } else if (errors.length === 1) {
                    setFileError(errors[0]);
                } else {
                    setFileError("The imported prompt has validation errors:");
                    setValidationErrors(errors);
                }
                return null;
            }

            // Check for truncation warnings
            const warnings = detectTruncationWarnings(result.data);
            setTruncationWarnings(warnings);

            return result.data;
        } catch {
            setFileError("Failed to read file. Please try again.");
            return null;
        }
    }, []);

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (!selectedFile) return;

        const data = await validateAndParseFile(selectedFile);

        if (data) {
            setImportData(data);
            setSelectedFileName(selectedFile.name);
            // Initialize the form with the imported command
            setValue("command", data.prompt.command || "");
        }

        // Reset file input
        if (e.target) {
            e.target.value = "";
        }
    };

    const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragging(false);
    };

    const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragging(false);

        const files = event.dataTransfer.files;
        if (files && files.length > 0) {
            const file = files[0];
            const data = await validateAndParseFile(file);

            if (data) {
                setImportData(data);
                setSelectedFileName(file.name);
                setValue("command", data.prompt.command || "");
            }
        }
    };

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const onSubmit = async (formData: PromptImportCommandForm) => {
        // Validate that a file has been selected
        if (!importData) {
            setFileError("Please select a JSON file to import");
            return;
        }

        setIsImporting(true);
        setFileError(null);

        try {
            // Update the import data with the edited command
            const updatedImportData: PromptImportData = {
                ...importData,
                prompt: {
                    ...importData.prompt,
                    command: formData.command || undefined,
                },
            };

            await onImport(updatedImportData, {
                preserveCommand: !!formData.command,
                preserveCategory: true, // Always preserve category
            });

            // Reset state and close dialog
            handleReset();
            onOpenChange(false);
        } catch (err) {
            setFileError(err instanceof Error ? err.message : "Failed to import prompt");
        } finally {
            setIsImporting(false);
        }
    };

    const handleReset = () => {
        setImportData(null);
        setSelectedFileName("");
        setFileError(null);
        setValidationErrors([]);
        setTruncationWarnings([]);
        resetForm();
    };

    const handleClose = () => {
        if (!isImporting) {
            handleReset();
            onOpenChange(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Import Prompt</DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 overflow-x-hidden py-4">
                    {/* File Upload - Drag and Drop or Selected File Display */}
                    {!selectedFileName ? (
                        <div
                            className={`flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center transition-all ${
                                isDragging ? "border-primary bg-primary/10 scale-[1.02]" : "border-muted-foreground/30"
                            }`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={handleUploadClick}
                        >
                            <FileJson className={`mb-3 h-10 w-10 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                            <p className={`mb-1 text-sm font-medium transition-colors ${isDragging ? "text-primary" : "text-foreground"}`}>{isDragging ? "Drop JSON file here" : "Drag and drop JSON file here"}</p>
                            <p className="text-muted-foreground text-xs">or click to browse</p>
                            <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".json" disabled={isImporting} className="hidden" />
                        </div>
                    ) : (
                        <div className="bg-muted/30 flex items-center gap-3 rounded-md border p-4">
                            <FileJson className="text-primary h-5 w-5 flex-shrink-0" />
                            <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium">{selectedFileName}</p>
                            </div>
                            <Button type="button" variant="ghost" size="sm" onClick={handleReset} disabled={isImporting}>
                                Change
                            </Button>
                        </div>
                    )}

                    {/* Error Display */}
                    {fileError && (
                        <div className="space-y-2">
                            <MessageBanner variant="error" message={fileError} />
                            {validationErrors.length > 0 && (
                                <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950/30">
                                    <ul className="list-inside list-disc space-y-1 text-sm text-red-800 dark:text-red-200">
                                        {validationErrors.map((err, idx) => (
                                            <li key={idx}>{err}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Preview */}
                    {importData && !fileError && (
                        <div className="space-y-4">
                            {truncationWarnings.length > 0 ? (
                                <Alert variant="destructive" className="border-amber-500 bg-amber-50 text-amber-900 dark:border-amber-600 dark:bg-amber-950/30 dark:text-amber-200 [&>svg]:text-amber-600">
                                    <AlertTriangle className="h-4 w-4" />
                                    <AlertDescription className="space-y-2">
                                        <p className="font-medium">Some fields exceed the maximum length and will be truncated:</p>
                                        <ul className="list-inside list-disc space-y-1 text-sm">
                                            {truncationWarnings.map((warning, idx) => (
                                                <li key={idx}>{warning.message}</li>
                                            ))}
                                        </ul>
                                    </AlertDescription>
                                </Alert>
                            ) : (
                                <Alert>
                                    <CheckCircle className="h-4 w-4" />
                                    <AlertDescription>File validated successfully. Review the details below:</AlertDescription>
                                </Alert>
                            )}

                            <div className="space-y-3 overflow-hidden rounded-lg border p-4">
                                <div>
                                    <Label className="text-muted-foreground text-xs">Name</Label>
                                    <p className="overflow-wrap-anywhere font-medium break-words">{importData.prompt.name}</p>
                                </div>

                                {importData.prompt.description && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Description</Label>
                                        <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.description}</p>
                                    </div>
                                )}

                                {importData.prompt.category && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Tag</Label>
                                        <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.category}</p>
                                    </div>
                                )}

                                {importData.prompt.command && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Command</Label>
                                        <p className="font-mono text-sm break-all">{importData.prompt.command}</p>
                                    </div>
                                )}

                                {importData.prompt.metadata?.authorName && (
                                    <div>
                                        <Label className="text-muted-foreground text-xs">Original Author</Label>
                                        <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.metadata.authorName}</p>
                                    </div>
                                )}
                            </div>

                            {/* Import Options */}
                            <div className="space-y-3 rounded-lg border p-4">
                                <Label className="text-sm font-medium">Import Options</Label>

                                {/* Editable Command Field */}
                                {importData.prompt.command && (
                                    <div className="space-y-2">
                                        <Label htmlFor="import-command" className="text-sm">
                                            Chat Shortcut
                                        </Label>
                                        <div className="flex items-center gap-2">
                                            <span className="text-muted-foreground text-sm">/</span>
                                            <Input id="import-command" {...register("command")} placeholder="e.g., code-review" className={`flex-1 ${errors.command ? "border-red-500" : ""}`} maxLength={PROMPT_FIELD_LIMITS.COMMAND_MAX} />
                                        </div>
                                        {errors.command && <p className="text-sm text-red-500">{errors.command.message}</p>}
                                        <p className="text-muted-foreground text-xs">
                                            You can modify the shortcut if needed (max {PROMPT_FIELD_LIMITS.COMMAND_MAX} characters). If it conflicts with an existing shortcut, a unique one will be generated automatically.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={handleClose} disabled={isImporting}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isImporting || !importData}>
                            {isImporting ? "Importing..." : "Import"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};
