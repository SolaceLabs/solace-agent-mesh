import { useState, useCallback } from 'react';
import { detectVariables, validatePromptText } from '@/lib/utils/promptUtils';
import { useChatContext } from '@/lib/hooks';

export interface TemplateConfig {
    name?: string;
    category?: string;
    command?: string;
    prompt_text?: string;
    description?: string;
    detected_variables?: string[];
}

export interface ValidationErrors {
    name?: string;
    command?: string;
    prompt_text?: string;
    [key: string]: string | undefined;
}

export function usePromptTemplateBuilder() {
    const { addNotification } = useChatContext();
    const [config, setConfig] = useState<TemplateConfig>({});
    const [validationErrors, setValidationErrors] = useState<ValidationErrors>({});
    const [isLoading, setIsLoading] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

    const updateConfig = useCallback((updates: Partial<TemplateConfig>) => {
        setConfig(prev => {
            const newConfig = { ...prev, ...updates };
            
            // Auto-detect variables when prompt_text changes
            if (updates.prompt_text !== undefined) {
                const variables = detectVariables(updates.prompt_text);
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
            errors.name = 'Template name is required';
        } else if (config.name.length > 255) {
            errors.name = 'Template name must be less than 255 characters';
        }

        // Validate command
        if (config.command) {
            if (!/^[a-zA-Z0-9_-]+$/.test(config.command)) {
                errors.command = 'Command can only contain letters, numbers, hyphens, and underscores';
            } else if (config.command.length > 50) {
                errors.command = 'Command must be less than 50 characters';
            }
        }

        // Validate prompt text
        if (!config.prompt_text || config.prompt_text.trim().length === 0) {
            errors.prompt_text = 'Prompt text is required';
        } else {
            const validation = validatePromptText(config.prompt_text);
            if (!validation.valid) {
                errors.prompt_text = validation.error || 'Invalid prompt text';
            }
        }

        setValidationErrors(errors);
        
        const isValid = Object.keys(errors).length === 0;
        
        // Show notification to user
        if (isValid) {
            addNotification('✓ Template is valid and ready to save!', 'success');
        } else {
            const errorMessages = Object.values(errors).join(', ');
            addNotification(`Validation failed: ${errorMessages}`, 'error');
        }
        
        return isValid;
    }, [config, addNotification]);

    const saveTemplate = useCallback(async (): Promise<boolean> => {
        setIsLoading(true);
        setSaveStatus('saving');

        try {
            // Validate first
            const isValid = await validateConfig();
            if (!isValid) {
                setSaveStatus('error');
                setIsLoading(false);
                return false;
            }

            // Prepare data for API
            const templateData = {
                name: config.name!,
                description: config.description || null,
                category: config.category || null,
                command: config.command || null,
                initial_prompt: config.prompt_text!,
            };

            // Call API to create prompt group
            const response = await fetch('/api/v1/prompts/groups', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(templateData),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to save template');
            }

            setSaveStatus('success');
            setIsLoading(false);
            return true;
        } catch (error) {
            console.error('Error saving template:', error);
            setSaveStatus('error');
            setIsLoading(false);
            
            // Set error message
            if (error instanceof Error) {
                setValidationErrors(prev => ({
                    ...prev,
                    _general: error.message,
                }));
            }
            
            return false;
        }
    }, [config, validateConfig]);

    const resetConfig = useCallback(() => {
        setConfig({});
        setValidationErrors({});
        setSaveStatus('idle');
    }, []);

    return {
        config,
        updateConfig,
        validateConfig,
        saveTemplate,
        resetConfig,
        validationErrors,
        isLoading,
        saveStatus,
    };
}