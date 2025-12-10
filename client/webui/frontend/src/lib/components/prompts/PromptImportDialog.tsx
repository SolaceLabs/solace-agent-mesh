import React, { useState, useRef, useCallback, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { FileJson } from "lucide-react";
import { z } from "zod";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Button, Input, Label } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components";
import type { PromptGroup } from "@/lib/types/prompts";
import { promptImportSchema, PROMPT_FIELD_LIMITS, formatZodErrors, hasPathError, getPathErrorMessage, detectTruncationWarnings, type PromptImportData, type TruncationWarning } from "@/lib/schemas";

// Schema for the editable fields in the import dialog (name and command)
const promptImportFormSchema = z.object({
    name: z.string().min(1, "Name is required").max(PROMPT_FIELD_LIMITS.NAME_MAX, `Name must be ${PROMPT_FIELD_LIMITS.NAME_MAX} characters or less`),
    command: z.string().max(PROMPT_FIELD_LIMITS.COMMAND_MAX, `Chat shortcut must be ${PROMPT_FIELD_LIMITS.COMMAND_MAX} characters or less`).optional().or(z.literal("")),
});

type PromptImportForm = z.infer<typeof promptImportFormSchema>;

interface ConflictInfo {
    hasNameConflict: boolean;
    hasCommandConflict: boolean;
}

interface PromptImportDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onImport: (data: PromptImportData, options: { preserveCommand: boolean; preserveCategory: boolean }) => Promise<void>;
    existingPrompts: PromptGroup[];
}

export const PromptImportDialog: React.FC<PromptImportDialogProps> = ({ open, onOpenChange, onImport, existingPrompts }) => {
    const [importData, setImportData] = useState<PromptImportData | null>(null);
    const [fileError, setFileError] = useState<string | null>(null);
    const [validationErrors, setValidationErrors] = useState<string[]>([]);
    const [truncationWarnings, setTruncationWarnings] = useState<TruncationWarning[]>([]);
    const [isImporting, setIsImporting] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFileName, setSelectedFileName] = useState<string>("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [initialNameConflict, setInitialNameConflict] = useState(false);
    const [initialCommandConflict, setInitialCommandConflict] = useState(false);

    // Form for the editable name and command fields
    const {
        register,
        handleSubmit,
        formState: { errors },
        reset: resetForm,
        setValue,
        watch,
    } = useForm<PromptImportForm>({
        resolver: zodResolver(promptImportFormSchema),
        defaultValues: {
            name: "",
            command: "",
        },
        mode: "onChange",
    });

    // Watch form values for conflict detection
    const watchedName = watch("name");
    const watchedCommand = watch("command");

    // Helper function to detect conflicts with existing prompts
    const detectConflicts = useCallback(
        (name: string, command: string): ConflictInfo => {
            const normalizedName = name.trim().toLowerCase();
            const normalizedCommand = command.trim().toLowerCase();

            let hasNameConflict = false;
            let hasCommandConflict = false;

            for (const prompt of existingPrompts) {
                // Check name conflict
                if (normalizedName && prompt.name?.toLowerCase() === normalizedName) {
                    hasNameConflict = true;
                }

                // Check command conflict (only if command is provided)
                if (normalizedCommand && prompt.command?.toLowerCase() === normalizedCommand) {
                    hasCommandConflict = true;
                }
            }

            return { hasNameConflict, hasCommandConflict };
        },
        [existingPrompts]
    );

    // Check for conflicts with existing prompts
    const conflicts = useMemo((): ConflictInfo => {
        if (!importData) {
            return { hasNameConflict: false, hasCommandConflict: false };
        }

        const currentName = watchedName || "";
        const currentCommand = watchedCommand || "";

        return detectConflicts(currentName, currentCommand);
    }, [importData, watchedName, watchedCommand, detectConflicts]);

    const hasConflicts = conflicts.hasNameConflict || conflicts.hasCommandConflict;

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

    // Check for initial conflicts when file is loaded
    const checkInitialConflicts = useCallback(
        (data: PromptImportData) => {
            const importedName = data.prompt.name || "";
            const importedCommand = data.prompt.command || "";

            const conflictInfo = detectConflicts(importedName, importedCommand);

            setInitialNameConflict(conflictInfo.hasNameConflict);
            setInitialCommandConflict(conflictInfo.hasCommandConflict);
        },
        [detectConflicts]
    );

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (!selectedFile) return;

        const data = await validateAndParseFile(selectedFile);

        if (data) {
            setImportData(data);
            setSelectedFileName(selectedFile.name);
            // Initialize the form with the imported name and command
            setValue("name", data.prompt.name || "");
            setValue("command", data.prompt.command || "");
            // Check for initial conflicts
            checkInitialConflicts(data);
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
                setValue("name", data.prompt.name || "");
                setValue("command", data.prompt.command || "");
                // Check for initial conflicts
                checkInitialConflicts(data);
            }
        }
    };

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const onSubmit = async (formData: PromptImportForm) => {
        // Validate that a file has been selected
        if (!importData) {
            setFileError("Please select a JSON file to import");
            return;
        }

        // Don't allow import if there are conflicts
        if (hasConflicts) {
            return;
        }

        setIsImporting(true);
        setFileError(null);

        try {
            // Update the import data with the edited name and command
            const updatedImportData: PromptImportData = {
                ...importData,
                prompt: {
                    ...importData.prompt,
                    name: formData.name,
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
        setInitialNameConflict(false);
        setInitialCommandConflict(false);
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
                            {/* Conflict Error Banner */}
                            {hasConflicts && (
                                <MessageBanner
                                    variant="error"
                                    message={
                                        <>
                                            <span className="font-medium">Conflicts found: </span>
                                            {conflicts.hasNameConflict && <span className="font-semibold">{watchedName}</span>}
                                            {conflicts.hasNameConflict && conflicts.hasCommandConflict && " name and "}
                                            {conflicts.hasCommandConflict && (
                                                <>
                                                    <span className="font-semibold">{watchedCommand}</span>
                                                    {" chat shortcut"}
                                                </>
                                            )}
                                            {conflicts.hasNameConflict && !conflicts.hasCommandConflict && " name"}
                                            {conflicts.hasNameConflict && conflicts.hasCommandConflict ? " already exist." : " already exists."}
                                        </>
                                    }
                                />
                            )}

                            {/* Truncation Warnings */}
                            {truncationWarnings.length > 0 && !hasConflicts && (
                                <MessageBanner
                                    variant="warning"
                                    message={
                                        <div className="space-y-2">
                                            <p className="font-medium">Some fields exceed the maximum length and will be truncated:</p>
                                            <ul className="list-inside list-disc space-y-1 text-sm">
                                                {truncationWarnings.map((warning, idx) => (
                                                    <li key={idx}>{warning.message}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    }
                                />
                            )}

                            {/* Review Prompt Section */}
                            <div className="flex flex-col gap-4">
                                <h3 className="text-sm font-semibold">Review Prompt</h3>

                                {/* Name Field - Editable when there's a conflict or was initially in conflict */}
                                <div className="space-y-1">
                                    <Label htmlFor="import-name" className="text-muted-foreground text-xs">
                                        Name{conflicts.hasNameConflict && <span className="text-destructive">*</span>}
                                    </Label>
                                    {initialNameConflict ? (
                                        <div className="space-y-2">
                                            <Input id="import-name" {...register("name")} className={`${errors.name || conflicts.hasNameConflict ? "border-red-500 focus-visible:ring-red-500" : ""}`} maxLength={PROMPT_FIELD_LIMITS.NAME_MAX} />
                                            {conflicts.hasNameConflict && !errors.name && <MessageBanner variant="error" message="Already exists. Change name." />}
                                            {errors.name && <p className="text-xs text-[#647481] dark:text-[#B1B9C0]">{errors.name.message}</p>}
                                        </div>
                                    ) : (
                                        <p className="overflow-wrap-anywhere text-sm break-words">{watchedName}</p>
                                    )}
                                </div>

                                {/* Description - Always read-only */}
                                <div className="space-y-1">
                                    <Label className="text-muted-foreground text-xs">Description</Label>
                                    {importData.prompt.description ? <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.description}</p> : <p className="text-muted-foreground text-sm italic">No description</p>}
                                </div>

                                {/* Tag - Always read-only */}
                                <div className="space-y-1">
                                    <Label className="text-muted-foreground text-xs">Tag</Label>
                                    {importData.prompt.category ? <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.category}</p> : <p className="text-muted-foreground text-sm italic">No tag</p>}
                                </div>

                                {/* Chat Shortcut Field - Editable when there's a conflict or was initially in conflict */}
                                <div className="space-y-1">
                                    <Label htmlFor="import-command" className="text-muted-foreground text-xs">
                                        Chat Shortcut{conflicts.hasCommandConflict && <span className="text-destructive">*</span>}
                                    </Label>
                                    {initialCommandConflict ? (
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-2">
                                                <span className="text-muted-foreground text-sm">/</span>
                                                <Input
                                                    id="import-command"
                                                    {...register("command")}
                                                    placeholder="e.g., code-review"
                                                    className={`flex-1 ${errors.command || conflicts.hasCommandConflict ? "border-red-500 focus-visible:ring-red-500" : ""}`}
                                                    maxLength={PROMPT_FIELD_LIMITS.COMMAND_MAX}
                                                />
                                            </div>
                                            {conflicts.hasCommandConflict && !errors.command && <MessageBanner variant="error" message="Already exists. Change chat shortcut." />}
                                            {errors.command && <p className="text-xs text-[#647481] dark:text-[#B1B9C0]">{errors.command.message}</p>}
                                        </div>
                                    ) : watchedCommand ? (
                                        <p className="font-mono text-sm break-all">{watchedCommand}</p>
                                    ) : (
                                        <p className="text-muted-foreground text-sm italic">No chat shortcut</p>
                                    )}
                                </div>

                                {/* Original Author - Always read-only */}
                                <div className="space-y-1">
                                    <Label className="text-muted-foreground text-xs">Original Author</Label>
                                    {importData.prompt.metadata?.authorName ? <p className="overflow-wrap-anywhere text-sm break-words">{importData.prompt.metadata.authorName}</p> : <p className="text-muted-foreground text-sm italic">No author</p>}
                                </div>
                            </div>
                        </div>
                    )}

                    <DialogFooter>
                        <Button type="button" variant="ghost" onClick={handleClose} disabled={isImporting}>
                            Cancel
                        </Button>
                        <Button data-testid="importPromptButton" type="submit" disabled={isImporting || !importData || hasConflicts}>
                            {isImporting ? "Importing..." : "Import"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};
