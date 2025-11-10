import React, { useRef, useState, useEffect, useMemo } from "react";
import type { ChangeEvent, FormEvent, ClipboardEvent } from "react";

import { Ban, Paperclip, Send } from "lucide-react";

import { Button, ChatInput, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { useChatContext, useDragAndDrop, useAgentSelection } from "@/lib/hooks";
import type { AgentCardInfo } from "@/lib/types";
import type { PromptGroup } from "@/lib/types/prompts";
import { detectVariables } from "@/lib/utils/promptUtils";

import { FileBadge } from "./file/FileBadge";
import { PromptsCommand } from "./PromptsCommand";
import { VariableDialog } from "./VariableDialog";
import {
    PastedTextBadge,
    PasteActionDialog,
    isLargeText,
    type PastedArtifactItem
} from "./paste";

export const ChatInputArea: React.FC<{ agents: AgentCardInfo[]; scrollToBottom?: () => void }> = ({ agents = [], scrollToBottom }) => {
    const { isResponding, isCancelling, selectedAgentName, sessionId, setSessionId, handleSubmit, handleCancel, uploadArtifactFile, artifactsRefetch, addNotification, artifacts, setPreviewArtifact, openSidePanelTab, messages } = useChatContext();
    const { handleAgentSelection } = useAgentSelection();

    // File selection support
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

    // Pasted artifact support
    const [pastedArtifactItems, setPastedArtifactItems] = useState<PastedArtifactItem[]>([]);
    const [pendingPasteContent, setPendingPasteContent] = useState<string | null>(null);
    const [showArtifactForm, setShowArtifactForm] = useState(false);

    const [contextText, setContextText] = useState<string | null>(null);

    const chatInputRef = useRef<HTMLTextAreaElement>(null);
    const prevIsRespondingRef = useRef<boolean>(isResponding);

    const [inputValue, setInputValue] = useState<string>("");
    
    const [showPromptsCommand, setShowPromptsCommand] = useState(false);
    
    const [showVariableDialog, setShowVariableDialog] = useState(false);
    const [pendingPromptGroup, setPendingPromptGroup] = useState<PromptGroup | null>(null);

    // Clear input when session changes (but keep track of previous session to avoid clearing on initial session creation)
    const prevSessionIdRef = useRef<string | null>(sessionId);
    
    useEffect(() => {
        // Check for pending prompt use on mount or session change
        const promptData = sessionStorage.getItem('pending-prompt-use');
        if (promptData) {
            sessionStorage.removeItem('pending-prompt-use');
            try {
                const { promptText, groupId, groupName } = JSON.parse(promptData);
                
                // Check if prompt has variables
                const variables = detectVariables(promptText);
                if (variables.length > 0) {
                    // Show variable dialog
                    setPendingPromptGroup({
                        id: groupId,
                        name: groupName,
                        production_prompt: { prompt_text: promptText }
                    } as PromptGroup);
                    setShowVariableDialog(true);
                } else {
                    setInputValue(promptText);
                    setTimeout(() => {
                        chatInputRef.current?.focus();
                    }, 100);
                }
            } catch (error) {
                console.error('Error parsing prompt data:', error);
            }
            return; // Don't clear input if we just set it
        }
        
        // Only clear if session actually changed (not just initialized)
        if (prevSessionIdRef.current && prevSessionIdRef.current !== sessionId) {
            setInputValue("");
            setShowPromptsCommand(false);
            setPastedArtifactItems([]);
        }
        prevSessionIdRef.current = sessionId;
        setContextText(null);
    }, [sessionId]);

    useEffect(() => {
        if (prevIsRespondingRef.current && !isResponding) {
            // Small delay to ensure the input is fully enabled
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
        }
        prevIsRespondingRef.current = isResponding;
    }, [isResponding]);

    // Focus the chat input when a new chat session is started
    useEffect(() => {
        const handleFocusChatInput = () => {
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
        };

        window.addEventListener("focus-chat-input", handleFocusChatInput);
        return () => {
            window.removeEventListener("focus-chat-input", handleFocusChatInput);
        };
    }, []);


    // Handle follow-up question from text selection
    useEffect(() => {
        const handleFollowUp = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { text, prompt, autoSubmit } = customEvent.detail;
            setContextText(text);
            
            // If a prompt is provided, pre-fill the input
            if (prompt) {
                setInputValue(prompt + " ");
                
                if (autoSubmit) {
                    // Small delay to ensure state is updated
                    setTimeout(async () => {
                        const fullMessage = `${prompt}\n\nContext: "${text}"`;
                        const fakeEvent = new Event('submit') as unknown as FormEvent;
                        await handleSubmit(fakeEvent, [], fullMessage);
                        setContextText(null);
                        setInputValue("");
                        scrollToBottom?.();
                    }, 50);
                    return;
                }
            }
            
            // Focus the input for custom questions
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
        };

        window.addEventListener('follow-up-question', handleFollowUp);
        return () => {
            window.removeEventListener('follow-up-question', handleFollowUp);
        };
    }, [handleSubmit, scrollToBottom]);

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

    const handlePaste = async (event: ClipboardEvent<HTMLTextAreaElement>) => {
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

        // Handle text pastes - show artifact form for large text
        const pastedText = clipboardData.getData('text');
        if (pastedText && isLargeText(pastedText)) {
            // Large text - show artifact creation form
            event.preventDefault();
            setPendingPasteContent(pastedText);
            setShowArtifactForm(true);
        }
        // Small text pastes go through normally (no preventDefault)
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

            // Upload the artifact
            const result = await uploadArtifactFile(file, sessionId, description);

            if (result) {
                // If a new session was created, update our sessionId
                if (result.sessionId && result.sessionId !== sessionId) {
                    setSessionId(result.sessionId);
                }
                
                // Create a badge item for this pasted artifact
                const artifactItem: PastedArtifactItem = {
                    id: `paste-artifact-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                    artifactId: result.uri,
                    filename: title,
                    timestamp: Date.now(),
                };
                setPastedArtifactItems(prev => {
                    return [...prev, artifactItem];
                });
                
                addNotification(`Artifact "${title}" created from pasted content.`);
                // Refresh artifacts panel
                await artifactsRefetch();
            } else {
                addNotification(`Failed to create artifact from pasted content.`, 'error');
            }
        } catch (error) {
            console.error('Error saving artifact:', error);
            addNotification(`Error creating artifact: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
        } finally {
            setPendingPasteContent(null);
            setShowArtifactForm(false);
        }
    };

    const handleCancelArtifactForm = () => {
        setPendingPasteContent(null);
        setShowArtifactForm(false);
    };

    const handleRemoveFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const isSubmittingEnabled = useMemo(
        () => !isResponding && (inputValue?.trim() || selectedFiles.length !== 0),
        [isResponding, inputValue, selectedFiles]
    );

    const onSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (isSubmittingEnabled) {
            let fullMessage = inputValue.trim()
            if (contextText) {
                fullMessage = `${fullMessage}\n\nContext: "${contextText}"`;
            }
            
            await handleSubmit(event, selectedFiles, fullMessage);
            setSelectedFiles([]);
            setPastedArtifactItems([]);
            setInputValue("");
            setContextText(null);
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

    // Handle reserved command
    const handleReservedCommand = (command: string, context?: string) => {
        if (command === 'create-template') {
            // Create enhanced message for AI builder
            const enhancedMessage = context
                ? `I want to create a reusable prompt template based on this conversation I just had:

<conversation_history>
${context}
</conversation_history>

Please help me create a prompt template by:

1. **Analyzing the Pattern**: Identify the core task/question pattern in this conversation
2. **Extracting Variables**: Determine which parts should be variables (use {{variable_name}} syntax)
3. **Generalizing**: Make it reusable for similar tasks
4. **Suggesting Metadata**: Recommend a name, description, category, and chat shortcut

Focus on capturing what made this conversation successful so it can be reused with different inputs.`
                : 'Help me create a new prompt template.';

            // Store in sessionStorage before dispatching event
            sessionStorage.setItem('pending-template-context', enhancedMessage);
            
            // Dispatch custom event to navigate to prompts page with context
            window.dispatchEvent(new CustomEvent('create-template-from-session', {
                detail: { initialMessage: enhancedMessage }
            }));
            
            // Clear input
            setInputValue('');
            setShowPromptsCommand(false);
        }
    };

    // Handle pasted artifact management
    const handleRemovePastedArtifact = (id: string) => {
        setPastedArtifactItems(prev => prev.filter(item => item.id !== id));
    };

    const handleViewPastedArtifact = (filename: string) => {
        // Find the artifact in the artifacts list
        const artifact = artifacts.find(a => a.filename === filename);
        if (artifact) {
            // Use the existing artifact preview functionality
            setPreviewArtifact(artifact);
            openSidePanelTab('files');
        }
    };

    // Handle variable dialog submission from "Use in Chat"
    const handleVariableSubmit = (processedPrompt: string) => {
        setInputValue(processedPrompt);
        setShowVariableDialog(false);
        setPendingPromptGroup(null);
        setTimeout(() => {
            chatInputRef.current?.focus();
        }, 100);
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

            {/* Pasted Artifact Items */}
            {(() => {
                return pastedArtifactItems.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-2">
                        {pastedArtifactItems.map((item, index) => (
                            <PastedTextBadge
                                key={item.id}
                                id={item.id}
                                index={index + 1}
                                textPreview={item.filename}
                                onClick={() => handleViewPastedArtifact(item.filename)}
                                onRemove={() => handleRemovePastedArtifact(item.id)}
                            />
                        ))}
                    </div>
                );
            })()}

            {/* Artifact Creation Dialog */}
            <PasteActionDialog
                isOpen={showArtifactForm}
                content={pendingPasteContent || ''}
                onSaveAsArtifact={handleSaveAsArtifact}
                onCancel={handleCancelArtifactForm}
                existingArtifacts={artifacts.map(a => a.filename)}
            />

            {/* Prompts Command Popover */}
            <PromptsCommand
                isOpen={showPromptsCommand}
                onClose={() => {
                    setShowPromptsCommand(false);
                }}
                textAreaRef={chatInputRef}
                onPromptSelect={handlePromptSelect}
                messages={messages}
                onReservedCommand={handleReservedCommand}
            />

            {/* Variable Dialog for "Use in Chat" */}
            {showVariableDialog && pendingPromptGroup && (
                <VariableDialog
                    group={pendingPromptGroup}
                    onSubmit={handleVariableSubmit}
                    onClose={() => {
                        setShowVariableDialog(false);
                        setPendingPromptGroup(null);
                    }}
                />
            )}

            {/* Chat Input */}
            <ChatInput
                ref={chatInputRef}
                value={inputValue}
                onChange={handleInputChange}
                placeholder="How can I help you today? (Type '/' to insert a prompt)"
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
                        <SelectValue placeholder="Select an agent..." />
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
