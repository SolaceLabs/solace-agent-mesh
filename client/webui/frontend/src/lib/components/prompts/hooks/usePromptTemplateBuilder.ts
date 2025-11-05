import { useState, useCallback } from 'react';
import { detectVariables, validatePromptText } from '@/lib/utils/promptUtils';
import { useChatContext } from '@/lib/hooks';
import type { PromptGroup } from '@/lib/types/prompts';

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

export function usePromptTemplateBuilder(editingGroup?: PromptGroup | null) {
    const { addNotification } = useChatContext();
    const [config, setConfig] = useState<TemplateConfig>(() => {
        if (editingGroup) {
            return {
                name: editingGroup.name,
                description: editingGroup.description,
                category: editingGroup.category,
                command: editingGroup.command,
                prompt_text: editingGroup.production_prompt?.prompt_text || '',
                detected_variables: detectVariables(editingGroup.production_prompt?.prompt_text || ''),
            };
        }
        return {};
    });
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
                const errorMessage = error.message || error.detail || 'Failed to save template';
                addNotification(errorMessage, 'error');
                throw new Error(errorMessage);
            }

            setSaveStatus('success');
            addNotification('Template saved successfully!', 'success');
            setIsLoading(false);
            return true;
        } catch (error) {
            console.error('Error saving template:', error);
            setSaveStatus('error');
            setIsLoading(false);
            
            // Show error notification
            if (error instanceof Error) {
                addNotification(error.message, 'error');
                setValidationErrors(prev => ({
                    ...prev,
                    _general: error.message,
                }));
            } else {
                addNotification('Failed to save template', 'error');
            }
            
            return false;
        }
    }, [config, validateConfig]);

    const updateTemplate = useCallback(async (groupId: string, createNewVersion: boolean): Promise<boolean> => {
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

            // Prepare update data
            const updateData: any = {};
            if (config.name !== editingGroup?.name) updateData.name = config.name;
            if (config.description !== editingGroup?.description) updateData.description = config.description;
            if (config.category !== editingGroup?.category) updateData.category = config.category;
            if (config.command !== editingGroup?.command) updateData.command = config.command;
            
            // Include prompt text only if creating new version
            if (createNewVersion && config.prompt_text !== editingGroup?.production_prompt?.prompt_text) {
                updateData.initial_prompt = config.prompt_text;
            }

            // Call API to update prompt group
            const response = await fetch(`/api/v1/prompts/groups/${groupId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(updateData),
            });

            if (!response.ok) {
                const error = await response.json();
                const errorMessage = error.message || error.detail || 'Failed to update template';
                addNotification(errorMessage, 'error');
                throw new Error(errorMessage);
            }

            setSaveStatus('success');
            const message = createNewVersion ? 'New version created successfully!' : 'Template updated successfully!';
            addNotification(message, 'success');
            setIsLoading(false);
            return true;
        } catch (error) {
            console.error('Error updating template:', error);
            setSaveStatus('error');
            setIsLoading(false);
            
            if (error instanceof Error) {
                addNotification(error.message, 'error');
            } else {
                addNotification('Failed to update template', 'error');
            }
            
            return false;
        }
    }, [config, editingGroup, validateConfig, addNotification]);

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
        updateTemplate,
        resetConfig,
        validationErrors,
        isLoading,
        saveStatus,
    };
}