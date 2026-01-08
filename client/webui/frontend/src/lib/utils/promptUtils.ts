/**
 * Utility functions for prompt library feature
 */

/**
 * Detects variables in prompt text using {{variable}} syntax
 * @param promptText The prompt text to analyze
 * @returns Array of unique variable names found
 */
export function detectVariables(promptText: string): string[] {
    const regex = /\{\{([^}]+)\}\}/g;
    const matches = promptText.matchAll(regex);
    const variables = new Set<string>();
    
    for (const match of matches) {
        variables.add(match[1].trim());
    }
    
    return Array.from(variables);
}

/**
 * Replaces variables in prompt text with provided values
 * @param promptText The prompt text with {{variables}}
 * @param values Object mapping variable names to their values
 * @returns Processed prompt text with variables replaced
 */
export function replaceVariables(
    promptText: string, 
    values: Record<string, string>
): string {
    let result = promptText;
    
    for (const [key, value] of Object.entries(values)) {
        const regex = new RegExp(`\\{\\{\\s*${key}\\s*\\}\\}`, 'g');
        result = result.replace(regex, value);
    }
    
    return result;
}

/**
 * Validates prompt text
 * @param text The prompt text to validate
 * @returns Validation result with error message if invalid
 */
export function validatePromptText(text: string): {
    valid: boolean;
    error?: string;
} {
    if (!text || text.trim().length === 0) {
        return { valid: false, error: 'Prompt text cannot be empty' };
    }
    
    if (text.length > 10000) {
        return { 
            valid: false, 
            error: 'Prompt text exceeds maximum length of 10,000 characters' 
        };
    }
    
    return { valid: true };
}

/**
 * Validates command format
 * @param command The command to validate
 * @returns Validation result with error message if invalid
 */
export function validateCommand(command: string): {
    valid: boolean;
    error?: string;
} {
    if (!command) {
        return { valid: true }; // Command is optional
    }
    
    if (command.length > 50) {
        return { 
            valid: false, 
            error: 'Command exceeds maximum length of 50 characters' 
        };
    }
    
    if (!/^[a-zA-Z0-9_-]+$/.test(command)) {
        return { 
            valid: false, 
            error: 'Command can only contain letters, numbers, hyphens, and underscores' 
        };
    }
    
    return { valid: true };
}

/**
 * Formats epoch millisecond timestamp for display
 * @param epochMs Timestamp in epoch milliseconds
 * @returns Formatted date string
 */
export function formatPromptDate(epochMs: number): string {
    const date = new Date(epochMs);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Extracts unique categories from prompt groups
 * @param groups Array of prompt groups
 * @returns Array of unique category names
 */
export function extractCategories(groups: Array<{ category?: string }>): string[] {
    const categories = new Set<string>();
    
    for (const group of groups) {
        if (group.category) {
            categories.add(group.category);
        }
    }
    
    return Array.from(categories).sort();
}

/**
 * Filters prompt groups by search term
 * @param groups Array of prompt groups
 * @param searchTerm Search term to filter by
 * @returns Filtered array of prompt groups
 */
export function filterPromptGroups(
    groups: Array<{
        name: string;
        description?: string;
        command?: string;
        category?: string;
    }>,
    searchTerm: string
): typeof groups {
    if (!searchTerm) return groups;
    
    const search = searchTerm.toLowerCase();
    return groups.filter(group => 
        group.name.toLowerCase().includes(search) ||
        group.description?.toLowerCase().includes(search) ||
        group.command?.toLowerCase().includes(search) ||
        group.category?.toLowerCase().includes(search)
    );
}