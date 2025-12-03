import { z } from "zod";

/**
 * Field length constraints matching backend validation
 * These values should be kept in sync with the backend DTO constraints
 */
export const PROMPT_FIELD_LIMITS = {
    NAME_MAX: 255,
    DESCRIPTION_MAX: 1000,
    TAG_MAX: 100,
    COMMAND_MAX: 50,
    AUTHOR_NAME_MAX: 255,
    PROMPT_TEXT_MAX: 10000,
} as const;

/**
 * Schema for prompt metadata within the import data
 * Note: originalVersion and originalCreatedAt are required when metadata is present
 * to match the existing interface in PromptsPage
 */
const promptMetadataSchema = z.object({
    authorName: z.union([z.string(), z.null()]).optional(),
    originalVersion: z.number().int().positive(),
    originalCreatedAt: z.number().int().positive(),
});

/**
 * Helper to create an optional string field that accepts null, undefined, or a valid string
 */
const optionalString = () => z.union([z.string(), z.null()]).optional();

/**
 * Schema for the prompt data within the import file
 * Note: Optional fields use union with z.null() to accept both undefined and null values
 * Note: We don't enforce max lengths here - the backend will truncate if needed
 * and we show warnings in the UI before import
 */
const promptDataSchema = z.object({
    name: z.string().min(1, "Name is required"),
    description: optionalString(),
    category: optionalString(),
    command: optionalString(),
    promptText: z.string().min(1, "Prompt text is required"),
    metadata: z.union([promptMetadataSchema, z.null()]).optional(),
});

/**
 * Schema for the complete prompt import file structure
 * Validates the exported JSON format including version and prompt data
 */
export const promptImportSchema = z.object({
    version: z.literal("1.0", {
        message: "Unsupported export format version. Only version 1.0 is currently supported.",
    }),
    exportedAt: z.number().int().positive("Export timestamp must be a valid positive number"),
    prompt: promptDataSchema,
});

/**
 * Schema for the editable command field in the import dialog
 */
export const promptImportCommandSchema = z.object({
    command: z.string().max(PROMPT_FIELD_LIMITS.COMMAND_MAX, `Command must be ${PROMPT_FIELD_LIMITS.COMMAND_MAX} characters or less`).optional().or(z.literal("")),
});

/**
 * Type inference from the schemas
 */
export type PromptImportData = z.infer<typeof promptImportSchema>;
export type PromptImportCommandForm = z.infer<typeof promptImportCommandSchema>;

/**
 * Represents a warning about a field that will be truncated during import
 */
export interface TruncationWarning {
    field: string;
    currentLength: number;
    maxLength: number;
    message: string;
}

/**
 * Checks if any fields in the import data will be truncated by the backend
 * and returns warnings for each field that exceeds the limit
 */
export function detectTruncationWarnings(data: PromptImportData): TruncationWarning[] {
    const warnings: TruncationWarning[] = [];
    const prompt = data.prompt;

    if (prompt.name && prompt.name.length > PROMPT_FIELD_LIMITS.NAME_MAX) {
        warnings.push({
            field: "Name",
            currentLength: prompt.name.length,
            maxLength: PROMPT_FIELD_LIMITS.NAME_MAX,
            message: `Name will be truncated from ${prompt.name.length} to ${PROMPT_FIELD_LIMITS.NAME_MAX} characters`,
        });
    }

    if (prompt.description && prompt.description.length > PROMPT_FIELD_LIMITS.DESCRIPTION_MAX) {
        warnings.push({
            field: "Description",
            currentLength: prompt.description.length,
            maxLength: PROMPT_FIELD_LIMITS.DESCRIPTION_MAX,
            message: `Description will be truncated from ${prompt.description.length} to ${PROMPT_FIELD_LIMITS.DESCRIPTION_MAX} characters`,
        });
    }

    if (prompt.category && prompt.category.length > PROMPT_FIELD_LIMITS.TAG_MAX) {
        warnings.push({
            field: "Tag",
            currentLength: prompt.category.length,
            maxLength: PROMPT_FIELD_LIMITS.TAG_MAX,
            message: `Tag will be truncated from ${prompt.category.length} to ${PROMPT_FIELD_LIMITS.TAG_MAX} characters`,
        });
    }

    if (prompt.command && prompt.command.length > PROMPT_FIELD_LIMITS.COMMAND_MAX) {
        warnings.push({
            field: "Command",
            currentLength: prompt.command.length,
            maxLength: PROMPT_FIELD_LIMITS.COMMAND_MAX,
            message: `Command will be truncated from ${prompt.command.length} to ${PROMPT_FIELD_LIMITS.COMMAND_MAX} characters`,
        });
    }

    if (prompt.promptText && prompt.promptText.length > PROMPT_FIELD_LIMITS.PROMPT_TEXT_MAX) {
        warnings.push({
            field: "Prompt text",
            currentLength: prompt.promptText.length,
            maxLength: PROMPT_FIELD_LIMITS.PROMPT_TEXT_MAX,
            message: `Prompt text will be truncated from ${prompt.promptText.length.toLocaleString()} to ${PROMPT_FIELD_LIMITS.PROMPT_TEXT_MAX.toLocaleString()} characters`,
        });
    }

    return warnings;
}

/**
 * Helper function to format zod validation errors for display
 * Compatible with zod v4 error structure
 */
export function formatZodErrors(error: z.ZodError): string[] {
    return error.issues.map(issue => {
        const path = issue.path.join(".");
        return path ? `${path}: ${issue.message}` : issue.message;
    });
}

/**
 * Helper function to check if a specific path has an error
 */
export function hasPathError(error: z.ZodError, pathSegment: string): boolean {
    return error.issues.some(issue => issue.path.includes(pathSegment));
}

/**
 * Helper function to get the first error message for a specific path
 */
export function getPathErrorMessage(error: z.ZodError, pathSegment: string): string | undefined {
    const issue = error.issues.find(issue => issue.path.includes(pathSegment));
    return issue?.message;
}
