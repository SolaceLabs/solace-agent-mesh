import React, { useRef, useState, useEffect, useMemo } from "react";
import type { ChangeEvent, FormEvent, ClipboardEvent } from "react";

import { Ban, Paperclip, Send } from "lucide-react";

import { Button, ChatInput, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { useChatContext, useDragAndDrop, useDebounce } from "@/lib/hooks";
import type { AgentCardInfo } from "@/lib/types";

import { FileBadge } from "./file/FileBadge";

export const ChatInputArea: React.FC<{ agents: AgentCardInfo[]; scrollToBottom?: () => void }> = ({ agents = [], scrollToBottom }) => {
    const { isResponding, isCancelling, userInput, selectedAgentName, setSelectedAgentName, setUserInput, handleSubmit, handleCancel } = useChatContext();

    // File selection support
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

    // Chat input ref for focus management
    const chatInputRef = useRef<HTMLTextAreaElement>(null);
    const prevIsRespondingRef = useRef<boolean>(isResponding);

    // Local state for input value before debouncing
    const [inputValue, setInputValue] = useState<string>(userInput);
    const debouncedInputValue = useDebounce<string>(inputValue, 300);

    useEffect(() => {
        setUserInput(debouncedInputValue);
    }, [debouncedInputValue, setUserInput]);

    // Sync inputValue when userInput changes (e.g., after form submission)
    useEffect(() => {
        setInputValue(userInput);
    }, [userInput]);

    // Focus the chat input when isResponding becomes false
    useEffect(() => {
        if (prevIsRespondingRef.current && !isResponding) {
            // Small delay to ensure the input is fully enabled
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
        }
        prevIsRespondingRef.current = isResponding;
    }, [isResponding]);

    const handleFileSelect = () => {
        if (!isResponding) {
            fileInputRef.current?.click();
        }
    };

    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files) {
            // Filter out duplicates based on name, size, and last modified time
            const newFiles = Array.from(files).filter(newFile => !selectedFiles.some(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size && existingFile.lastModified === newFile.lastModified));
            if (newFiles.length > 0) {
                setSelectedFiles(prev => [...prev, ...newFiles]);
            }
        }

        if (event.target) {
            event.target.value = "";
        }

        setTimeout(() => {
            chatInputRef.current?.focus();
        }, 100);
    };

    const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
        if (isResponding) return;

        const clipboardData = event.clipboardData;
        if (!clipboardData || !clipboardData.files || clipboardData.files.length === 0) return;

        if (clipboardData.files.length > 0) {
            event.preventDefault(); // Prevent the default paste behavior for files
        }

        // Filter out duplicates based on name, size, and last modified time
        const newFiles = Array.from(clipboardData.files).filter(newFile => !selectedFiles.some(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size && existingFile.lastModified === newFile.lastModified));
        if (newFiles.length > 0) {
            setSelectedFiles(prev => [...prev, ...newFiles]);
        }
    };

    const handleRemoveFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const isSubmittingEnabled = useMemo(() => !isResponding && (inputValue?.trim() || selectedFiles.length !== 0), [isResponding, inputValue, selectedFiles]);

    const onSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (isSubmittingEnabled) {
            await handleSubmit(event, selectedFiles, inputValue.trim());
            setSelectedFiles([]);
            setInputValue("");
            scrollToBottom?.();
        }
    };

    const handleFilesDropped = (files: File[]) => {
        if (isResponding) return;

        // Filter out duplicates based on name, size, and last modified time
        const newFiles = files.filter(newFile => !selectedFiles.some(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size && existingFile.lastModified === newFile.lastModified));

        if (newFiles.length > 0) {
            setSelectedFiles(prev => [...prev, ...newFiles]);
        }
    };

    const { isDragging, handleDragEnter, handleDragOver, handleDragLeave, handleDrop } = useDragAndDrop({
        onFilesDropped: handleFilesDropped,
        disabled: isResponding,
    });

    return (
        <div
            className={`rounded-lg border p-4 shadow-sm ${isDragging ? "border-dotted border-[var(--primary-wMain)] bg-[var(--accent-background)]" : ""}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {/* Hidden File Input */}
            <input type="file" ref={fileInputRef} className="hidden" multiple onChange={handleFileChange} accept="*/*" disabled={isResponding} />

            {/* Selected Files */}
            {selectedFiles.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                    {selectedFiles.map((file, index) => (
                        <FileBadge key={`${file.name}-${file.lastModified}-${index}`} fileName={file.name} onRemove={() => handleRemoveFile(index)} />
                    ))}
                </div>
            )}

            {/* Chat Input */}
            <ChatInput
                ref={chatInputRef}
                value={inputValue}
                onChange={event => setInputValue(event.target.value)}
                placeholder="How can I help you today?"
                className="field-sizing-content max-h-50 min-h-0 resize-none rounded-2xl border-none p-3 text-base/normal shadow-none transition-[height] duration-500 ease-in-out focus-visible:outline-none"
                rows={1}
                onPaste={handlePaste}
                onKeyDown={event => {
                    if (event.key === "Enter" && !event.shiftKey && isSubmittingEnabled) {
                        onSubmit(event);
                    }
                }}
            />

            {/* Buttons */}
            <div className="m-2 flex items-center gap-2">
                <Button variant="ghost" onClick={handleFileSelect} disabled={isResponding} tooltip="Attach file">
                    <Paperclip className="size-4" />
                </Button>

                <div>Agent: </div>
                <Select value={selectedAgentName} onValueChange={setSelectedAgentName} disabled={isResponding || agents.length === 0}>
                    <SelectTrigger className="w-[250px]">
                        <SelectValue defaultValue={selectedAgentName} />
                    </SelectTrigger>
                    <SelectContent>
                        {agents.map(agent => (
                            <SelectItem key={agent.name} value={agent.name}>
                                {agent.displayName || agent.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                {isResponding && !isCancelling ? (
                    <Button className="ml-auto gap-1.5" onClick={handleCancel} variant="outline" disabled={isCancelling} tooltip="Cancel">
                        <Ban className="size-4" />
                        Stop
                    </Button>
                ) : (
                    <Button variant="ghost" className="ml-auto gap-1.5" onClick={onSubmit} disabled={!isSubmittingEnabled} tooltip="Send message">
                        <Send className="size-4" />
                    </Button>
                )}
            </div>
        </div>
    );
};
