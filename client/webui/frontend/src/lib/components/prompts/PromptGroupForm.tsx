/**
 * PromptGroupForm Component
 * Form for creating or editing a prompt group
 */

import React, { useState, useEffect } from 'react';
import type { PromptGroup, PromptGroupCreate, PromptGroupUpdate } from '@/lib/types/prompts';
import { Dialog, DialogContent, DialogHeader, DialogTitle, Button, Label } from '@/lib/components/ui';
import { validateCommand, validatePromptText } from '@/lib/utils/promptUtils';

interface PromptGroupFormProps {
    group?: PromptGroup | null;
    onSubmit: (data: PromptGroupCreate | PromptGroupUpdate) => void;
    onClose: () => void;
}

export const PromptGroupForm: React.FC<PromptGroupFormProps> = ({
    group,
    onSubmit,
    onClose,
}) => {
    const isEditing = !!group;
    
    const [formData, setFormData] = useState({
        name: group?.name || '',
        description: group?.description || '',
        category: group?.category || '',
        command: group?.command || '',
        initial_prompt: group?.production_prompt?.prompt_text || '',
    });
    
    const [errors, setErrors] = useState<Record<string, string>>({});

    // Update form when group changes
    useEffect(() => {
        if (group) {
            setFormData({
                name: group.name || '',
                description: group.description || '',
                category: group.category || '',
                command: group.command || '',
                initial_prompt: group.production_prompt?.prompt_text || '',
            });
        }
    }, [group]);

    const validate = (): boolean => {
        const newErrors: Record<string, string> = {};
        
        if (!formData.name.trim()) {
            newErrors.name = 'Name is required';
        }
        
        if (formData.command) {
            const commandValidation = validateCommand(formData.command);
            if (!commandValidation.valid) {
                newErrors.command = commandValidation.error || 'Invalid command';
            }
        }
        
        if (!isEditing && !formData.initial_prompt.trim()) {
            newErrors.initial_prompt = 'Initial prompt is required';
        }
        
        if (formData.initial_prompt) {
            const promptValidation = validatePromptText(formData.initial_prompt);
            if (!promptValidation.valid) {
                newErrors.initial_prompt = promptValidation.error || 'Invalid prompt text';
            }
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!validate()) return;
        
        if (isEditing) {
            // For editing, send changed fields including prompt text
            const updateData: any = {};
            if (formData.name !== group?.name) updateData.name = formData.name;
            if (formData.description !== group?.description) updateData.description = formData.description;
            if (formData.category !== group?.category) updateData.category = formData.category;
            if (formData.command !== group?.command) updateData.command = formData.command;
            
            // Include prompt text if changed (will trigger new version creation)
            if (formData.initial_prompt !== group?.production_prompt?.prompt_text) {
                updateData.initial_prompt = formData.initial_prompt;
            }
            
            onSubmit(updateData);
        } else {
            // For creating, send all fields
            const createData: PromptGroupCreate = {
                name: formData.name,
                description: formData.description || undefined,
                category: formData.category || undefined,
                command: formData.command || undefined,
                initial_prompt: formData.initial_prompt,
            };
            
            onSubmit(createData);
        }
    };

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{isEditing ? 'Edit Prompt' : 'Create New Prompt'}</DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Name */}
                    <div className="space-y-2">
                        <Label htmlFor="name" className="text-sm font-medium">
                            Name <span className="text-red-500">*</span>
                        </Label>
                        <input
                            id="name"
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="e.g., Code Review Helper"
                            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
                            autoFocus
                        />
                        {errors.name && <p className="text-xs text-red-500">{errors.name}</p>}
                    </div>

                    {/* Description */}
                    <div className="space-y-2">
                        <Label htmlFor="description" className="text-sm font-medium">
                            Description
                        </Label>
                        <input
                            id="description"
                            type="text"
                            value={formData.description}
                            onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                            placeholder="Short description of what this prompt does"
                            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
                        />
                        {errors.description && <p className="text-xs text-red-500">{errors.description}</p>}
                    </div>

                    {/* Category */}
                    <div className="space-y-2">
                        <Label htmlFor="category" className="text-sm font-medium">
                            Category
                        </Label>
                        <input
                            id="category"
                            type="text"
                            value={formData.category}
                            onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                            placeholder="e.g., Development, Writing, Analysis"
                            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
                        />
                        {errors.category && <p className="text-xs text-red-500">{errors.category}</p>}
                    </div>

                    {/* Command */}
                    <div className="space-y-2">
                        <Label htmlFor="command" className="text-sm font-medium">
                            Command Shortcut
                        </Label>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-[var(--muted-foreground)]">/</span>
                            <input
                                id="command"
                                type="text"
                                value={formData.command}
                                onChange={(e) => setFormData(prev => ({ ...prev, command: e.target.value }))}
                                placeholder="e.g., review, summarize"
                                className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
                            />
                        </div>
                        <p className="text-xs text-[var(--muted-foreground)]">
                            Optional shortcut to quickly access this prompt (letters, numbers, dash, underscore only)
                        </p>
                        {errors.command && <p className="text-xs text-red-500">{errors.command}</p>}
                    </div>

                    {/* Prompt Text */}
                    <div className="space-y-2">
                        <Label htmlFor="initial_prompt" className="text-sm font-medium">
                            Prompt Text <span className="text-red-500">*</span>
                        </Label>
                        <textarea
                            id="initial_prompt"
                            value={formData.initial_prompt}
                            onChange={(e) => setFormData(prev => ({ ...prev, initial_prompt: e.target.value }))}
                            placeholder="Enter your prompt here. Use {{variable_name}} for variables."
                            rows={8}
                            className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] resize-y"
                        />
                        <p className="text-xs text-[var(--muted-foreground)]">
                            {isEditing
                                ? 'Editing the prompt text will create a new version automatically.'
                                : `Tip: Use {{variable_name}} to create fillable variables`
                            }
                        </p>
                        {errors.initial_prompt && <p className="text-xs text-red-500">{errors.initial_prompt}</p>}
                    </div>

                    {/* Buttons */}
                    <div className="flex justify-end gap-2 pt-4">
                        <Button type="button" variant="outline" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit">
                            {isEditing ? 'Update' : 'Create'}
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    );
};