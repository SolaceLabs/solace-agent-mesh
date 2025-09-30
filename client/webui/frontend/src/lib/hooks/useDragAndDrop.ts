import { useState, useCallback, useRef, type DragEvent } from "react";

interface UseDragAndDropOptions {
    onFilesDropped: (files: File[]) => void;
    fileFilter?: (file: File) => boolean;
    isDuplicate?: (newFile: File, existingFiles: File[]) => boolean;
    disabled?: boolean;
}

interface UseDragAndDropResult {
    isDragging: boolean;
    handleDragEnter: (event: DragEvent<HTMLElement>) => void;
    handleDragOver: (event: DragEvent<HTMLElement>) => void;
    handleDragLeave: (event: DragEvent<HTMLElement>) => void;
    handleDrop: (event: DragEvent<HTMLElement>) => void;
}

/**
 * Custom hook for handling file drag and drop functionality
 */
export const useDragAndDrop = ({ onFilesDropped, fileFilter, disabled = false }: UseDragAndDropOptions): UseDragAndDropResult => {
    const [isDragging, setIsDragging] = useState<boolean>(false);
    const dragCounter = useRef<number>(0);

    const handleDragEnter = useCallback(
        (event: DragEvent<HTMLElement>) => {
            if (disabled) return;

            event.preventDefault();
            event.stopPropagation();

            dragCounter.current = (dragCounter.current || 0) + 1;

            if (event.dataTransfer.types.includes("Files")) {
                setIsDragging(true);
            }
        },
        [disabled, dragCounter]
    );

    const handleDragOver = useCallback(
        (event: DragEvent<HTMLElement>) => {
            if (disabled) return;

            event.preventDefault();
            event.stopPropagation();

            // Set dropEffect to copy to show the user that dropping is allowed
            if (event.dataTransfer.types.includes("Files")) {
                event.dataTransfer.dropEffect = "copy";
            }
        },
        [disabled]
    );

    const handleDragLeave = useCallback(
        (event: DragEvent<HTMLElement>) => {
            if (disabled) return;

            event.preventDefault();
            event.stopPropagation();

            dragCounter.current = (dragCounter.current || 0) - 1;

            // Only set isDragging to false if counter reaches 0
            if (dragCounter.current === 0) {
                setIsDragging(false);
            }
        },
        [disabled, dragCounter]
    );

    const handleDrop = useCallback(
        (event: DragEvent<HTMLElement>) => {
            if (disabled) return;

            event.preventDefault();
            event.stopPropagation();

            setIsDragging(false);
            dragCounter.current = 0;

            // Check if files were dropped
            if (!event.dataTransfer.files || event.dataTransfer.files.length === 0) {
                return;
            }

            // Convert FileList to array
            const droppedFiles = Array.from(event.dataTransfer.files);

            // Apply file filter if provided
            const filteredFiles = fileFilter ? droppedFiles.filter(fileFilter) : droppedFiles;

            if (filteredFiles.length === 0) {
                return;
            }

            onFilesDropped(filteredFiles);
        },
        [disabled, dragCounter, fileFilter, onFilesDropped]
    );

    return {
        isDragging,
        handleDragEnter,
        handleDragOver,
        handleDragLeave,
        handleDrop,
    };
};
