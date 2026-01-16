// ============================================================================
// Mock File Creation Helpers
// ============================================================================

/**
 * Creates a mock File object for testing
 * @param name - The filename
 * @param size - The file size in bytes
 * @param type - The MIME type
 * @returns A File object with the specified properties
 */
export const createMockFile = (name: string, size: number, type: string): File => {
    const blob = new Blob(["a".repeat(size)], { type });
    return new File([blob], name, { type });
};

/**
 * Creates a mock FileList object from an array of Files
 * @param files - Array of File objects
 * @returns A FileList-like object that can be used in tests
 */
export const createMockFileList = (files: File[]): FileList => {
    const fileList: Record<number, File> & {
        length: number;
        item: (index: number) => File | null;
        [Symbol.iterator]: () => IterableIterator<File>;
    } = {
        length: files.length,
        item: (index: number) => files[index] || null,
        [Symbol.iterator]: function* () {
            for (const f of files) {
                yield f;
            }
        },
    };
    files.forEach((file, index) => {
        fileList[index] = file;
    });
    return fileList as FileList;
};
