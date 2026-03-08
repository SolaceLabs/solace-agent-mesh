/**
 * File validation utilities for consistent file size validation across the application.
 */

import { formatBytes } from "./format";

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

export interface ProjectSizeLimitValidationResult {
    valid: boolean;
    error?: string;
    currentSize: number;
    newSize: number;
    totalSize: number;
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
    const maxSizeWithUnit = formatBytes(maxSizeBytes, 0);
    let errorMsg: string;

    if (oversizedFiles.length === 1) {
        const file = oversizedFiles[0];
        if (includeFileSizes) {
            const fileSizeWithUnit = formatBytes(file.size);
            errorMsg = `File "${file.name}" (${fileSizeWithUnit}) exceeds the maximum size of ${maxSizeWithUnit}.`;
        } else {
            errorMsg = `File "${file.name}" exceeds the maximum size of ${maxSizeWithUnit}.`;
        }
    } else {
        const fileList = oversizedFiles.slice(0, maxFilesToList);
        const fileNames = includeFileSizes ? fileList.map(f => `${f.name} (${formatBytes(f.size)})`) : fileList.map(f => f.name);

        const remaining = oversizedFiles.length - maxFilesToList;
        const suffix = remaining > 0 ? ` and ${remaining} more` : "";

        errorMsg = `${oversizedFiles.length} files exceed the maximum size of ${maxSizeWithUnit}: ${fileNames.join(", ")}${suffix}`;
    }

    return {
        valid: false,
        error: errorMsg,
        oversizedFiles,
    };
}

/**
 * Validates that the batch upload size doesn't exceed the limit.
 * This is independent of the total project size.
 *
 * @param files - FileList or array of Files to validate
 * @param maxBatchUploadSizeBytes - Maximum batch upload size limit
 * @returns Validation result with error message if batch exceeds limit
 */
export function validateBatchUploadSize(files: FileList | File[], maxBatchUploadSizeBytes?: number): FileSizeValidationResult {
    if (!maxBatchUploadSizeBytes) {
        return { valid: true };
    }

    const totalBatchSize = calculateTotalFileSize(files);

    if (totalBatchSize <= maxBatchUploadSizeBytes) {
        return { valid: true };
    }

    const totalBatchWithUnit = formatBytes(totalBatchSize);
    const limitWithUnit = formatBytes(maxBatchUploadSizeBytes, 0);

    return {
        valid: false,
        error: `Batch upload size (${totalBatchWithUnit}) exceeds limit of ${limitWithUnit}. Please upload fewer files at once.`,
    };
}

/**
 * Calculates the total size of multiple files in bytes.
 *
 * @param files - Some list of Files, or Array of objects with size property
 * @returns Total size in bytes
 */
export function calculateTotalFileSize(files: FileList | File[] | Array<{ size: number }>): number {
    const fileArray: Array<{ size: number }> = Array.isArray(files) ? files : Array.from(files);
    return fileArray.reduce((sum, file) => sum + file.size, 0);
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
    const actualSizeWithUnit = formatBytes(actualSize);
    const maxSizeWithUnit = formatBytes(maxSize);
    return `File "${filename}" is too large: ${actualSizeWithUnit} exceeds the maximum allowed size of ${maxSizeWithUnit}.`;
}

/**
 * Validates total project size: existing files + new files <= maxProjectSizeBytes
 * This enforces a project-level storage limit, not a per-request limit.
 *
 * @param currentProjectSizeBytes - Current total size of project artifacts in bytes
 * @param newFiles - FileList or array of Files to be uploaded
 * @param maxProjectSizeBytes - Maximum total project size limit
 * @returns Validation result with error message if limit would be exceeded
 */
export function validateProjectSizeLimit(currentProjectSizeBytes: number, newFiles: FileList | File[], maxProjectSizeBytes?: number): ProjectSizeLimitValidationResult {
    const newSize = calculateTotalFileSize(newFiles);
    const totalSize = currentProjectSizeBytes + newSize;

    if (!maxProjectSizeBytes) {
        return { valid: true, currentSize: currentProjectSizeBytes, newSize, totalSize };
    }

    if (totalSize <= maxProjectSizeBytes) {
        return { valid: true, currentSize: currentProjectSizeBytes, newSize, totalSize };
    }

    const currentWithUnit = formatBytes(currentProjectSizeBytes);
    const newWithUnit = formatBytes(newSize);
    const totalWithUnit = formatBytes(totalSize);
    const limitWithUnit = formatBytes(maxProjectSizeBytes, 0);

    return {
        valid: false,
        currentSize: currentProjectSizeBytes,
        newSize,
        totalSize,
        error: `Project size limit exceeded. Current: ${currentWithUnit}, New files: ${newWithUnit}, Total: ${totalWithUnit} exceeds limit of ${limitWithUnit}.`,
    };
}
