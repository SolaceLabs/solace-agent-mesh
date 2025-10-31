import React, { useRef, useState, useEffect, useMemo } from "react";
import type { ChangeEvent, FormEvent, ClipboardEvent } from "react";

import { Ban, Paperclip, Send } from "lucide-react";

import { Button, ChatInput, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { useChatContext, useDragAndDrop, useAgentSelection } from "@/lib/hooks";
import type { AgentCardInfo } from "@/lib/types";

import { FileBadge } from "./file/FileBadge";
import { PromptsCommand } from "./PromptsCommand";
import { PastedTextBadge, PastedTextDialog, PasteActionDialog, isLargeText, createPastedTextItem, getTextPreview, type PastedTextItem } from "./paste";

export const ChatInputArea: React.FC<{ agents: AgentCardInfo[]; scrollToBottom?: () => void }> = ({ agents = [], scrollToBottom }) => {
    const { isResponding, isCancelling, selectedAgentName, sessionId, setSessionId, handleSubmit, handleCancel, uploadArtifactFile, artifactsRefetch, addNotification, artifacts } = useChatContext();
    const { handleAgentSelection } = useAgentSelection();

    // File selection support
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

    // Pasted text support
    const [pastedTextItems, setPastedTextItems] = useState<PastedTextItem[]>([]);
    const [selectedPasteId, setSelectedPasteId] = useState<string | null>(null);
    const [pendingPasteContent, setPendingPasteContent] = useState<string | null>(null);
    const [showPasteActionDialog, setShowPasteActionDialog] = useState(false);

    // Chat input ref for focus management
    const chatInputRef = useRef<HTMLTextAreaElement>(null);
    const prevIsRespondingRef = useRef<boolean>(isResponding);

    // Local state for input value (no debouncing needed!)
    const [inputValue, setInputValue] = useState<string>("");
    
    // Prompts command state
    const [showPromptsCommand, setShowPromptsCommand] = useState(false);

    // Clear input when session changes
    useEffect(() => {
        setInputValue("");
        setShowPromptsCommand(false);
        setPastedTextItems([]);
        setSelectedPasteId(null);
    }, [sessionId]);

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
        if (!clipboardData) return;

        // Handle file pastes (existing logic)
        if (clipboardData.files && clipboardData.files.length > 0) {
            event.preventDefault(); // Prevent the default paste behavior for files
            
            // Filter out duplicates based on name, size, and last modified time
            const newFiles = Array.from(clipboardData.files).filter(newFile =>
                !selectedFiles.some(existingFile =>
                    existingFile.name === newFile.name &&
                    existingFile.size === newFile.size &&
                    existingFile.lastModified === newFile.lastModified
                )
            );
            if (newFiles.length > 0) {
                setSelectedFiles(prev => [...prev, ...newFiles]);
            }
            return;
        }

        // Handle text pastes - show action dialog for large text
        const pastedText = clipboardData.getData('text');
        if (pastedText && isLargeText(pastedText)) {
            event.preventDefault(); // Prevent default paste for large text
            setPendingPasteContent(pastedText);
            setShowPasteActionDialog(true);
        }
        // Small text pastes go through normally (no preventDefault)
    };

    const handleRemoveFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const isSubmittingEnabled = useMemo(
        () => !isResponding && (inputValue?.trim() || selectedFiles.length !== 0 || pastedTextItems.length !== 0),
        [isResponding, inputValue, selectedFiles, pastedTextItems]
    );

    const onSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (isSubmittingEnabled) {
            // Combine input value with pasted text items
            const pastedTexts = pastedTextItems.map(item => item.content).join('\n\n');
            const fullMessage = [inputValue.trim(), pastedTexts]
                .filter(Boolean)
                .join('\n\n');
            
            await handleSubmit(event, selectedFiles, fullMessage);
            setSelectedFiles([]);
            setPastedTextItems([]);
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

    // Handle input change with "/" detection
    const handleInputChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        const value = event.target.value;
        setInputValue(value);
        
        // Check if "/" is typed at start or after space
        const cursorPosition = event.target.selectionStart;
        const textBeforeCursor = value.substring(0, cursorPosition);
        const lastChar = textBeforeCursor[textBeforeCursor.length - 1];
        const charBeforeLast = textBeforeCursor[textBeforeCursor.length - 2];
        
        if (lastChar === '/' && (!charBeforeLast || charBeforeLast === ' ' || charBeforeLast === '\n')) {
            setShowPromptsCommand(true);
        } else if (showPromptsCommand && !textBeforeCursor.includes('/')) {
            setShowPromptsCommand(false);
        }
    };

    // Handle prompt selection
    const handlePromptSelect = (promptText: string) => {
        // Remove the "/" trigger and insert the prompt
        const cursorPosition = chatInputRef.current?.selectionStart || 0;
        const textBeforeCursor = inputValue.substring(0, cursorPosition);
        const textAfterCursor = inputValue.substring(cursorPosition);
        
        // Find the last "/" before cursor
        const lastSlashIndex = textBeforeCursor.lastIndexOf('/');
        const newText = textBeforeCursor.substring(0, lastSlashIndex) + promptText + textAfterCursor;
        
        setInputValue(newText);
        setShowPromptsCommand(false);
        
        // Focus back on input
        setTimeout(() => {
            chatInputRef.current?.focus();
        }, 100);
    };

    // Handle pasted text management
    const handleRemovePastedText = (id: string) => {
        setPastedTextItems(prev => prev.filter(item => item.id !== id));
    };

    const handleViewPastedText = (id: string) => {
        setSelectedPasteId(id);
    };

    const handleClosePastedTextDialog = () => {
        setSelectedPasteId(null);
    };

    // Handle paste action dialog
    const handlePasteAsText = () => {
        if (pendingPasteContent) {
            const newItem = createPastedTextItem(pendingPasteContent);
            setPastedTextItems(prev => [...prev, newItem]);
        }
        setPendingPasteContent(null);
        setShowPasteActionDialog(false);
    };

    const handleSaveAsArtifact = async (title: string, fileType: string, description?: string) => {
        if (!pendingPasteContent) return;

        try {
            // Determine MIME type
            let mimeType = 'text/plain';
            if (fileType !== 'auto') {
                mimeType = fileType;
            }

            // Create a File object from the text content
            const blob = new Blob([pendingPasteContent], { type: mimeType });
            const file = new File([blob], title, { type: mimeType });

            // Upload the artifact - uploadArtifactFile will create a session if needed
            // and return the sessionId in the result
            const result = await uploadArtifactFile(file, sessionId, description);

            if (result) {
                // If a new session was created, update our sessionId
                if (result.sessionId && result.sessionId !== sessionId) {
                    setSessionId(result.sessionId);
                    console.log(`Session created via artifact upload: ${result.sessionId}`);
                }
                
                addNotification(`Artifact "${title}" created successfully.`);
                // Refresh artifacts panel
                await artifactsRefetch();
                
                // Optionally open the files panel to show the new artifact
                // openSidePanelTab('files');
            } else {
                addNotification(`Failed to create artifact "${title}".`, 'error');
            }
        } catch (error) {
            console.error('Error saving artifact:', error);
            addNotification(`Error creating artifact: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
        } finally {
            setPendingPasteContent(null);
            setShowPasteActionDialog(false);
        }
    };

    const handleCancelPasteAction = () => {
        setPendingPasteContent(null);
        setShowPasteActionDialog(false);
    };

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

            {/* Pasted Text Items */}
            {pastedTextItems.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                    {pastedTextItems.map((item, index) => (
                        <PastedTextBadge
                            key={item.id}
                            id={item.id}
                            index={index + 1}
                            textPreview={getTextPreview(item.content)}
                            onClick={() => handleViewPastedText(item.id)}
                            onRemove={() => handleRemovePastedText(item.id)}
                        />
                    ))}
                </div>
            )}

            {/* Pasted Text Dialog */}
            <PastedTextDialog
                isOpen={selectedPasteId !== null}
                onClose={handleClosePastedTextDialog}
                content={pastedTextItems.find(item => item.id === selectedPasteId)?.content || ''}
                title="Pasted Text Content"
            />

            {/* Paste Action Dialog */}
            <PasteActionDialog
                isOpen={showPasteActionDialog}
                content={pendingPasteContent || ''}
                onPasteAsText={handlePasteAsText}
                onSaveAsArtifact={handleSaveAsArtifact}
                onCancel={handleCancelPasteAction}
                existingArtifacts={artifacts.map(a => a.filename)}
            />

            {/* Prompts Command Popover */}
            <PromptsCommand
                isOpen={showPromptsCommand}
                onClose={() => setShowPromptsCommand(false)}
                textAreaRef={chatInputRef}
                onPromptSelect={handlePromptSelect}
            />

            {/* Chat Input */}
            <ChatInput
                ref={chatInputRef}
                value={inputValue}
                onChange={handleInputChange}
                placeholder="How can I help you today? (Type / for prompts)"
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
                <Select value={selectedAgentName} onValueChange={handleAgentSelection} disabled={isResponding || agents.length === 0}>
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
                    <Button data-testid="cancel" className="ml-auto gap-1.5" onClick={handleCancel} variant="outline" disabled={isCancelling} tooltip="Cancel">
                        <Ban className="size-4" />
                        Stop
                    </Button>
                ) : (
                    <Button data-testid="sendMessage" variant="ghost" className="ml-auto gap-1.5" onClick={onSubmit} disabled={!isSubmittingEnabled} tooltip="Send message">
                        <Send className="size-4" />
                    </Button>
                )}
            </div>
        </div>
    );
};
