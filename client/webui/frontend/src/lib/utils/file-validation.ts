/**
 * File validation utilities for consistent file size validation across the application.
 */

export interface FileSizeValidationResult {
    valid: boolean;
    error?: string;
    oversizedFiles?: Array<{ name: string; size: number }>;
}

export interface FileSizeValidationOptions {
    /** Maximum file size in bytes. If not provided, validation is skipped. */
    maxSizeBytes?: number;
    /** Custom error message prefix. Defaults to "File" or "files" */
    errorPrefix?: string;
    /** Whether to include file sizes in the error message */
    includeFileSizes?: boolean;
    /** Maximum number of files to list in error message before truncating */
    maxFilesToList?: number;
}

/**
 * Validates file sizes against a maximum limit.
 *
 * @param files - FileList or array of Files to validate
 * @param options - Validation options including max size and error formatting
 * @returns Validation result with error message if any files exceed the limit
 *
 * @example
 * ```ts
 * const result = validateFileSizes(files, { maxSizeBytes: 50 * 1024 * 1024 });
 * if (!result.valid) {
 *   setError(result.error);
 * }
 * ```
 */
export function validateFileSizes(files: FileList | File[], options: FileSizeValidationOptions = {}): FileSizeValidationResult {
    const { maxSizeBytes, includeFileSizes = true, maxFilesToList = 3 } = options;

    // Skip validation if max size is not configured
    if (!maxSizeBytes) {
        return { valid: true };
    }

    const fileArray = Array.from(files);
    const oversizedFiles: Array<{ name: string; size: number }> = [];

    for (const file of fileArray) {
        if (file.size > maxSizeBytes) {
            oversizedFiles.push({ name: file.name, size: file.size });
        }
    }

    if (oversizedFiles.length === 0) {
        return { valid: true };
    }

    // Build error message
    const maxSizeMB = (maxSizeBytes / (1024 * 1024)).toFixed(0);
    let errorMsg: string;

    if (oversizedFiles.length === 1) {
        const file = oversizedFiles[0];
        if (includeFileSizes) {
            const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
            errorMsg = `File "${file.name}" (${fileSizeMB} MB) exceeds the maximum size of ${maxSizeMB} MB.`;
        } else {
            errorMsg = `File "${file.name}" exceeds the maximum size of ${maxSizeMB} MB.`;
        }
    } else {
        const fileList = oversizedFiles.slice(0, maxFilesToList);
        const fileNames = includeFileSizes ? fileList.map(f => `${f.name} (${(f.size / (1024 * 1024)).toFixed(2)} MB)`) : fileList.map(f => f.name);

        const remaining = oversizedFiles.length - maxFilesToList;
        const suffix = remaining > 0 ? ` and ${remaining} more` : "";

        errorMsg = `${oversizedFiles.length} files exceed the maximum size of ${maxSizeMB} MB: ${fileNames.join(", ")}${suffix}`;
    }

    return {
        valid: false,
        error: errorMsg,
        oversizedFiles,
    };
}

/**
 * Formats a file size in bytes to a human-readable string.
 *
 * @param bytes - File size in bytes
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string like "1.5 MB" or "500 KB"
 */
export function formatFileSize(bytes: number, decimals: number = 2): string {
    if (bytes === 0) return "0 Bytes";

    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}

/**
 * Checks if a single file exceeds the maximum size limit.
 *
 * @param file - File to check
 * @param maxSizeBytes - Maximum allowed size in bytes
 * @returns true if file is within limit, false if it exceeds
 */
export function isFileSizeValid(file: File, maxSizeBytes?: number): boolean {
    if (!maxSizeBytes) return true;
    return file.size <= maxSizeBytes;
}

/**
 * Creates a detailed error message for a file that exceeds the size limit.
 * Useful for displaying in error dialogs or notifications.
 *
 * @param filename - Name of the file
 * @param actualSize - Actual file size in bytes
 * @param maxSize - Maximum allowed size in bytes
 * @returns Formatted error message
 */
export function createFileSizeErrorMessage(filename: string, actualSize: number, maxSize: number): string {
    const actualSizeMB = (actualSize / (1024 * 1024)).toFixed(2);
    const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(2);
    return `File "${filename}" is too large: ${actualSizeMB} MB exceeds the maximum allowed size of ${maxSizeMB} MB.`;
}
