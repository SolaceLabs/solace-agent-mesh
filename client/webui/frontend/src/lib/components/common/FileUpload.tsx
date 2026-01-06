import { useState, useRef, useEffect, type DragEvent, type ChangeEvent } from "react";
import { X } from "lucide-react";

import { Button } from "@/lib/components";
import { MessageBanner } from "@/lib/components/common";

/**
 * Removes a file at the specified index from a FileList.
 * @param prevFiles the FileList
 * @param indexToRemove the index of the file to remove
 * @returns new FileList with the file removed, or null if no files remain
 */
const removeAtIndex = (prevFiles: FileList | null, indexToRemove: number): FileList | null => {
    if (!prevFiles) return null;
    const filesArray = Array.from(prevFiles);
    filesArray.splice(indexToRemove, 1);
    if (filesArray.length === 0) {
        return null;
    }
    const dataTransfer = new DataTransfer();
    filesArray.forEach(file => dataTransfer.items.add(file));
    return dataTransfer.files;
};

export interface FileUploadProps {
    name: string;
    accept: string;
    multiple?: boolean;
    disabled?: boolean;
    testid?: string;
    value?: FileList | null;
    onChange: (file: FileList | null) => void;
    onValidate?: (files: FileList) => { valid: boolean; error?: string };
}

function FileUpload({ name, accept, multiple = false, disabled = false, testid = "", value = null, onChange, onValidate }: FileUploadProps) {
    const [uploadedFiles, setUploadedFiles] = useState<FileList | null>(value);
    const [isDragging, setIsDragging] = useState(false);
    const [validationError, setValidationError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Sync internal state with value prop to handle external clearing
    useEffect(() => {
        setUploadedFiles(value);
    }, [value]);

    const setSelectedFiles = (files: FileList | null) => {
        if (files && files.length > 0) {
            // Validate files if validation function is provided
            if (onValidate) {
                const validation = onValidate(files);
                if (!validation.valid) {
                    setValidationError(validation.error || "File validation failed.");
                    if (fileInputRef.current) {
                        fileInputRef.current.value = "";
                    }
                    return;
                }
            }

            setValidationError(null);
            setUploadedFiles(files);
            onChange(files);
        } else {
            setValidationError(null);
            setUploadedFiles(null);
            onChange(null);
            fileInputRef.current!.value = "";
        }
    };

    const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        if (disabled) {
            e.currentTarget.style.cursor = "not-allowed";
        } else {
            e.currentTarget.style.cursor = "default";
        }
    };

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);

        if (!disabled) {
            let files = e.dataTransfer.files;

            // If multiple is false and more than one file is dropped, only take the first file
            if (!multiple && files.length > 1) {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(files[0]);
                files = dataTransfer.files;
            }

            setSelectedFiles(files);
        }
    };

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        setSelectedFiles(files);
    };

    const handleDropZoneClick = (e: React.MouseEvent<HTMLButtonElement>) => {
        e.preventDefault();
        fileInputRef.current?.click();
    };

    const handleClearValidationError = () => {
        setValidationError(null);
    };

    const handleRemoveFile = (index: number) => {
        const newFiles = removeAtIndex(uploadedFiles, index);
        setUploadedFiles(newFiles);
        onChange(newFiles);

        // Clear the input so the same file can be re-selected
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    return (
        <div>
            {validationError && (
                <div className="mb-3">
                    <MessageBanner variant="error" message={validationError} dismissible onDismiss={handleClearValidationError} />
                </div>
            )}
            <input ref={fileInputRef} name={name} type="file" multiple={multiple} disabled={disabled} onChange={handleFileChange} className="hidden" accept={accept} data-testid={testid} />
            {uploadedFiles ? (
                Array.from(uploadedFiles).map((file, index) => (
                    <div key={file.name} className="var(--tw-border-style) flex h-[48px] flex-row items-center rounded-sm border-1 pr-2 pl-4 text-[var(--color-secondary-text-wMain)]">
                        <div className="flex-1 font-semibold">{file.name}</div>
                        <Button variant="ghost" size="sm" onClick={() => handleRemoveFile(index)} aria-label={`Remove file ${file.name}`}>
                            <X />
                        </Button>
                    </div>
                ))
            ) : (
                <div
                    className={`flex h-[140px] flex-col justify-center rounded-sm border-1 border-dashed transition-colors ${isDragging ? "border-[var(--color-brand-wMain)] hover:border-solid" : "border-[var(--color-secondary-w40)]"}`}
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    role="dropzone"
                >
                    {isDragging && !disabled ? (
                        <div className="pointer-events-none text-center text-[var(--color-primary-text-wMain)]">Drop file here</div>
                    ) : (
                        <div className="pointer-events-none text-center text-[var(--color-secondary-text-wMain)]">
                            <div>Drag and drop file here</div>
                            <div className="mt-2 mb-2 flex flex-row items-center justify-center">
                                <div className="mr-1 h-[1px] w-[125px] bg-[var(--color-secondary-w40)]"></div>
                                <div>OR</div>
                                <div className="ml-1 h-[1px] w-[125px] bg-[var(--color-secondary-w40)]"></div>
                            </div>
                            <div>
                                <Button className="pointer-events-auto" variant="ghost" disabled={disabled} onClick={handleDropZoneClick}>
                                    Upload File
                                </Button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export { FileUpload };
