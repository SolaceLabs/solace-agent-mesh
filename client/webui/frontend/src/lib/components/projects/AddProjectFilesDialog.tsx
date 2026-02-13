import React, { useCallback, useEffect } from "react";
import { useForm } from "react-hook-form";

import { Textarea } from "@/lib/components/ui";
import { Form, FormField, FormItem, FormControl, FormError, FormMessage } from "@/lib/components/ui/form";
import { MessageBanner, ConfirmationDialog } from "@/lib/components/common";
import { FileLabel } from "../chat/file/FileLabel";
import { useConfigContext } from "@/lib/hooks";
import { DEFAULT_MAX_FILE_DESCRIPTION_LENGTH } from "@/lib/constants/validation";
import { cn } from "@/lib/utils";

interface AddProjectFilesDialogProps {
    isOpen: boolean;
    files: FileList | null;
    onClose: () => void;
    onConfirm: (formData: FormData) => void;
    isSubmitting?: boolean;
    error?: string | null;
    onClearError?: () => void;
}

export const AddProjectFilesDialog: React.FC<AddProjectFilesDialogProps> = ({ isOpen, files, onClose, onConfirm, isSubmitting = false, error = null, onClearError }) => {
    const { validationLimits } = useConfigContext();
    const FILE_DESCRIPTION_MAX = validationLimits?.projectFileDescriptionMax ?? DEFAULT_MAX_FILE_DESCRIPTION_LENGTH;

    const form = useForm<Record<string, string>>({
        mode: "onChange",
        defaultValues: {},
    });

    useEffect(() => {
        if (isOpen && files) {
            const defaults: Record<string, string> = {};
            Array.from(files).forEach((_, index) => {
                defaults[index.toString()] = "";
            });
            form.reset(defaults);
        }
    }, [isOpen, files, form]);

    const handleClose = useCallback(() => {
        onClearError?.();
        onClose();
    }, [onClose, onClearError]);

    const handleConfirmClick = useCallback(() => {
        if (!files) return;

        const formData = new FormData();
        const fileDescriptions = form.getValues();
        const metadataPayload: Record<string, string> = {};

        Array.from(files).forEach((file, index) => {
            formData.append("files", file);
            const description = fileDescriptions[index.toString()];
            if (description?.trim()) {
                metadataPayload[file.name] = description.trim();
            }
        });

        if (Object.keys(metadataPayload).length > 0) {
            formData.append("fileMetadata", JSON.stringify(metadataPayload));
        }

        onConfirm(formData);
    }, [files, form, onConfirm]);

    const fileList = files ? Array.from(files) : [];

    const hasErrors = error || Object.keys(form.formState.errors).length > 0;

    const dialogContent = (
        <>
            {error && <MessageBanner variant="error" message={error} dismissible onDismiss={onClearError} />}
            {fileList.length > 0 ? (
                <Form {...form}>
                    <div className="mt-4 flex max-h-[50vh] flex-col gap-4 overflow-y-auto p-1">
                        {fileList.map((file, index) => {
                            const fieldName = index.toString();
                            const currentValue = form.watch(fieldName) || "";

                            return (
                                <FormField
                                    key={fieldName}
                                    control={form.control}
                                    name={fieldName}
                                    rules={{
                                        maxLength: {
                                            value: FILE_DESCRIPTION_MAX,
                                            message: `Description must not exceed ${FILE_DESCRIPTION_MAX} characters`,
                                        },
                                    }}
                                    render={({ field, fieldState }) => (
                                        <FormItem>
                                            <FileLabel fileName={file.name} fileSize={file.size} />
                                            <FormControl>
                                                <Textarea {...field} rows={2} disabled={isSubmitting} maxLength={FILE_DESCRIPTION_MAX + 1} className={cn("mt-2 resize-none text-sm", fieldState.error && "border-destructive")} />
                                            </FormControl>
                                            <FormError />
                                            {!fieldState.error && (
                                                <FormMessage>
                                                    {currentValue.length} / {FILE_DESCRIPTION_MAX}
                                                </FormMessage>
                                            )}
                                        </FormItem>
                                    )}
                                />
                            );
                        })}
                    </div>
                </Form>
            ) : (
                <p className="text-muted-foreground">No files selected.</p>
            )}
        </>
    );

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={open => !open && handleClose()}
            title="Upload Project Files"
            description="Add descriptions to help Solace Agent Mesh understand each file's purpose."
            content={dialogContent}
            actionLabels={{
                cancel: "Cancel",
                confirm: `Upload ${fileList.length} File(s)`,
            }}
            isLoading={isSubmitting}
            isEnabled={!hasErrors}
            onConfirm={handleConfirmClick}
            onCancel={handleClose}
        />
    );
};
