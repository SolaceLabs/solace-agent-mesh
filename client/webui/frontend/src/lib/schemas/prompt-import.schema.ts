import { z } from "zod";

/**
 * Field length constraints matching backend validation
 * These values should be kept in sync with the backend DTO constraints
 */
export const PROMPT_FIELD_LIMITS = {
    NAME_MAX: 255,
    DESCRIPTION_MAX: 500,
    CATEGORY_MAX: 100,
    COMMAND_MAX: 50,
    AUTHOR_NAME_MAX: 255,
} as const;

/**
 * Schema for prompt metadata within the import data
 * Note: originalVersion and originalCreatedAt are required when metadata is present
 * to match the existing interface in PromptsPage
 */
const promptMetadataSchema = z.object({
    authorName: z.union([z.string().max(PROMPT_FIELD_LIMITS.AUTHOR_NAME_MAX, `Author name must be ${PROMPT_FIELD_LIMITS.AUTHOR_NAME_MAX} characters or less`), z.null()]).optional(),
    originalVersion: z.number().int().positive(),
    originalCreatedAt: z.number().int().positive(),
});

/**
 * Helper to create an optional string field that accepts null, undefined, or a valid string
 */
const optionalString = (maxLength: number, fieldName: string) => z.union([z.string().max(maxLength, `${fieldName} must be ${maxLength} characters or less`), z.null()]).optional();

/**
 * Schema for the prompt data within the import file
 * Note: Optional fields use union with z.null() to accept both undefined and null values
 */
const promptDataSchema = z.object({
    name: z.string().min(1, "Name is required").max(PROMPT_FIELD_LIMITS.NAME_MAX, `Name must be ${PROMPT_FIELD_LIMITS.NAME_MAX} characters or less`),
    description: optionalString(PROMPT_FIELD_LIMITS.DESCRIPTION_MAX, "Description"),
    category: optionalString(PROMPT_FIELD_LIMITS.CATEGORY_MAX, "Category"),
    command: optionalString(PROMPT_FIELD_LIMITS.COMMAND_MAX, "Command"),
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
