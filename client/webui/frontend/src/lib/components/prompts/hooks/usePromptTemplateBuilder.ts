import { useState, useCallback } from "react";
import { useChatContext } from "@/lib/hooks";
import { getErrorMessage } from "@/lib/utils";
import { detectVariables, validatePromptText } from "@/lib/utils/promptUtils";
import type { PromptGroup, TemplateConfig } from "@/lib/types/prompts";
import { isReservedCommand } from "@/lib/constants/reservedCommands";
import { api } from "@/lib/api";

export interface ValidationErrors {
    name?: string;
    command?: string;
    promptText?: string;
    [key: string]: string | undefined;
}

export function usePromptTemplateBuilder(editingGroup?: PromptGroup | null) {
    const { addNotification } = useChatContext();
    const [config, setConfig] = useState<TemplateConfig>(() => {
        if (editingGroup) {
            return {
                name: editingGroup.name,
                description: editingGroup.description,
                category: editingGroup.category,
                command: editingGroup.command,
                promptText: editingGroup.productionPrompt?.promptText || "",
                detected_variables: detectVariables(editingGroup.productionPrompt?.promptText || ""),
            };
        }
        return {};
    });
    const [validationErrors, setValidationErrors] = useState<ValidationErrors>({});
    const [isLoading, setIsLoading] = useState(false);
    const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");

    const updateConfig = useCallback((updates: Partial<TemplateConfig>) => {
        setConfig(prev => {
            const newConfig = { ...prev, ...updates };

            // Auto-detect variables when promptText changes
            if (updates.promptText !== undefined) {
                const variables = detectVariables(updates.promptText || "");
                newConfig.detected_variables = variables;
            }

            return newConfig;
        });

        // Clear validation errors for updated fields
        setValidationErrors(prev => {
            const newErrors = { ...prev };
            Object.keys(updates).forEach(key => {
                delete newErrors[key];
            });
            return newErrors;
        });
    }, []);

    const validateConfig = useCallback(async (): Promise<boolean> => {
        const errors: ValidationErrors = {};

        // Validate name
        if (!config.name || config.name.trim().length === 0) {
            errors.name = "Template name is required";
        } else if (config.name.length > 255) {
            errors.name = "Template name must be less than 255 characters";
        }

        // Validate command (now required)
        if (!config.command || config.command.trim().length === 0) {
            errors.command = "Chat shortcut is required";
        } else if (!/^[a-zA-Z0-9_-]+$/.test(config.command)) {
            errors.command = "Command can only contain letters, numbers, hyphens, and underscores";
        } else if (config.command.length > 50) {
            errors.command = "Command must be less than 50 characters";
        } else if (isReservedCommand(config.command)) {
            errors.command = `'${config.command}' is a reserved command and cannot be used`;
        }

        // Validate prompt text
        if (!config.promptText || config.promptText.trim().length === 0) {
            errors.promptText = "Prompt text is required";
        } else {
            const validation = validatePromptText(config.promptText);
            if (!validation.valid) {
                errors.promptText = validation.error || "Invalid prompt text";
            }
        }

        setValidationErrors(errors);

        const isValid = Object.keys(errors).length === 0;

        // Show notification to user only if valid (errors are shown in the UI banner)
        if (isValid) {
            addNotification("Template is valid and ready to save!", "success");
        }

        return isValid;
    }, [config, addNotification]);

    const saveTemplate = useCallback(async (): Promise<string | null> => {
        setIsLoading(true);
        setSaveStatus("saving");

        try {
            // Validate first
            const isValid = await validateConfig();
            if (!isValid) {
                setSaveStatus("error");
                setIsLoading(false);
                return null;
            }

            // Prepare data for API
            const templateData = {
                name: config.name!,
                description: config.description || null,
                category: config.category || null,
                command: config.command || null,
                initial_prompt: config.promptText!,
            };

            // Call API to create prompt group
            const createdGroup = await api.webui.post("/api/v1/prompts/groups", templateData);

            setSaveStatus("success");
            addNotification("Template saved", "success");
            setIsLoading(false);
            return createdGroup.id;
        } catch (error) {
            console.error("Error saving template:", error);
            setSaveStatus("error");
            setIsLoading(false);

            // Store error in validation errors for display
            const errorMessage = getErrorMessage(error, "Failed to save template");
            setValidationErrors(prev => ({
                ...prev,
                _general: errorMessage,
            }));

            return null;
        }
    }, [config, validateConfig, addNotification]);

    const updateTemplate = useCallback(
        async (groupId: string, createNewVersion: boolean = false): Promise<boolean> => {
            setIsLoading(true);
            setSaveStatus("saving");

            try {
                // Validate first
                const isValid = await validateConfig();
                if (!isValid) {
                    setSaveStatus("error");
                    setIsLoading(false);
                    return false;
                }

                // Build update data with all fields
                const updateData: Record<string, unknown> = {};
                if (config.name !== editingGroup?.name) updateData.name = config.name;
                if (config.description !== editingGroup?.description) updateData.description = config.description;
                if (config.category !== editingGroup?.category) updateData.category = config.category;
                if (config.command !== editingGroup?.command) updateData.command = config.command;
                updateData.initial_prompt = config.promptText;
                updateData.create_new_version = createNewVersion;

                await api.webui.patch(`/api/v1/prompts/groups/${groupId}`, updateData);

                setSaveStatus("success");
                addNotification(createNewVersion ? "New version created" : "Changes saved", "success");
                setIsLoading(false);
                return true;
            } catch (error) {
                console.error("Error updating template:", error);
                setSaveStatus("error");
                setIsLoading(false);

                // Store error in validation errors for display
                const errorMessage = getErrorMessage(error, "Failed to update template");
                setValidationErrors(prev => ({
                    ...prev,
                    _general: errorMessage,
                }));

                return false;
            }
        },
        [config, editingGroup, validateConfig, addNotification]
    );

    const resetConfig = useCallback(() => {
        setConfig({});
        setValidationErrors({});
        setSaveStatus("idle");
    }, []);

    return {
        config,
        updateConfig,
        validateConfig,
        saveTemplate,
        updateTemplate,
        resetConfig,
        validationErrors,
        isLoading,
        saveStatus,
    };
}
