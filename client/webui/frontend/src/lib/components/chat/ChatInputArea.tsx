import React, { useRef, useState, useEffect, useMemo, useCallback } from "react";
import type { ChangeEvent, FormEvent, ClipboardEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import { Ban, Paperclip, Send, MessageSquarePlus } from "lucide-react";

import { Button, ChatInput, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { useChatContext, useDragAndDrop, useAgentSelection, useAudioSettings, useConfigContext } from "@/lib/hooks";
import type { AgentCardInfo } from "@/lib/types";
import type { PromptGroup } from "@/lib/types/prompts";
import { detectVariables } from "@/lib/utils/promptUtils";

import { FileBadge } from "./file/FileBadge";
import { AudioRecorder } from "./AudioRecorder";
import { PromptsCommand, type ChatCommand } from "./PromptsCommand";
import { VariableDialog } from "./VariableDialog";
import { PendingPastedTextBadge, PasteActionDialog, isLargeText, createPastedTextItem, type PasteMetadata, type PastedTextItem } from "./paste";
import { getErrorMessage } from "@/lib/utils";

const createEnhancedMessage = (command: ChatCommand, conversationContext?: string): string => {
    switch (command) {
        case "create-template":
            if (!conversationContext) {
                return "Help me create a new prompt template.";
            }

            return [
                "I want to create a reusable prompt template based on this conversation I just had:",
                "",
                "<conversation_history>",
                conversationContext,
                "</conversation_history>",
                "",
                "Please help me create a prompt template by:",
                "",
                "1. **Analyzing the Pattern**: Identify the core task/question pattern in this conversation",
                "2. **Extracting Variables**: Determine which parts should be variables (use {{variable_name}} syntax)",
                "3. **Generalizing**: Make it reusable for similar tasks",
                "4. **Suggesting Metadata**: Recommend a name, description, category, and chat shortcut",
                "",
                "Focus on capturing what made this conversation successful so it can be reused with different inputs.",
            ].join("\n");
        default:
            return "";
    }
};

export const ChatInputArea: React.FC<{ agents: AgentCardInfo[]; scrollToBottom?: () => void }> = ({ agents = [], scrollToBottom }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const { isResponding, isCancelling, selectedAgentName, sessionId, setSessionId, handleSubmit, handleCancel, uploadArtifactFile, displayError, artifacts, messages, startNewChatWithPrompt, pendingPrompt, clearPendingPrompt } = useChatContext();
    const { handleAgentSelection } = useAgentSelection();
    const { settings } = useAudioSettings();
    const { configFeatureEnablement } = useConfigContext();

    // Feature flags
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;

    // File selection support
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

    // Pending pasted text support (not yet saved as artifacts, shown as badges)
    // These items may have optional metadata if user has configured them via dialog
    const [pendingPastedTextItems, setPendingPastedTextItems] = useState<PastedTextItem[]>([]);
    const [selectedPendingPasteId, setSelectedPendingPasteId] = useState<string | null>(null);
    const [showArtifactForm, setShowArtifactForm] = useState(false);

    const [contextText, setContextText] = useState<string | null>(null);
    const [showContextBadge, setShowContextBadge] = useState(false);

    const chatInputRef = useRef<HTMLTextAreaElement>(null);
    const prevIsRespondingRef = useRef<boolean>(isResponding);

    const [inputValue, setInputValue] = useState<string>("");

    const [showPromptsCommand, setShowPromptsCommand] = useState(false);

    const [showVariableDialog, setShowVariableDialog] = useState(false);
    const [pendingPromptGroup, setPendingPromptGroup] = useState<PromptGroup | null>(null);

    // STT error state for persistent banner
    const [sttError, setSttError] = useState<string | null>(null);

    // Track recording state to disable input
    const [isRecording, setIsRecording] = useState(false);

    // Clear input when session changes (but keep track of previous session to avoid clearing on initial session creation)
    const prevSessionIdRef = useRef<string | null>(sessionId);

    // Flag to track if we've already processed the current location state
    const processedLocationStateRef = useRef<string | null>(null);

    // Handle pending prompt use from router state - delegate to ChatProvider
    useEffect(() => {
        if (location.state?.promptText && processedLocationStateRef.current !== location.state.groupId) {
            const { promptText, groupId, groupName } = location.state;

            // Mark this state as being processed to prevent re-triggering
            processedLocationStateRef.current = groupId;

            // Clear the location state immediately
            navigate(location.pathname, { replace: true, state: {} });

            // Delegate to ChatProvider to handle the new session with prompt
            startNewChatWithPrompt({ promptText, groupId, groupName });

            // Reset the processed state ref after a delay to allow for future uses
            setTimeout(() => {
                processedLocationStateRef.current = null;
            }, 1000);
        }
    }, [location.state, location.pathname, navigate, startNewChatWithPrompt]);

    // Apply pending prompt from ChatProvider when session is ready
    useEffect(() => {
        if (pendingPrompt && selectedAgentName) {
            const { promptText, groupId, groupName } = pendingPrompt;

            // Check if prompt has variables
            const variables = detectVariables(promptText);
            if (variables.length > 0) {
                // Show variable dialog
                setPendingPromptGroup({
                    id: groupId,
                    name: groupName,
                    productionPrompt: { promptText },
                } as PromptGroup);
                setShowVariableDialog(true);
            } else {
                setInputValue(promptText);
                setTimeout(() => {
                    chatInputRef.current?.focus();
                }, 100);
            }

            // Clear the pending prompt from provider
            clearPendingPrompt();
        }
    }, [pendingPrompt, selectedAgentName, clearPendingPrompt]);

    // Handle session changes (for normal session switching, not prompt template usage)
    useEffect(() => {
        // Skip if there's a pending prompt being processed
        if (pendingPrompt) {
            prevSessionIdRef.current = sessionId;
            return;
        }

        // Only clear if session actually changed (not just initialized) and no pending prompt
        if (prevSessionIdRef.current && prevSessionIdRef.current !== sessionId) {
            setInputValue("");
            setShowPromptsCommand(false);
            setPendingPastedTextItems([]);
        }
        prevSessionIdRef.current = sessionId;
        setContextText(null);
    }, [pendingPrompt, sessionId]);

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

            // If a prompt is provided, use the old behavior
            if (prompt) {
                setContextText(text);
                setInputValue(prompt + " ");

                if (autoSubmit) {
                    // Small delay to ensure state is updated
                    setTimeout(async () => {
                        const fullMessage = `${prompt}\n\nContext: "${text}"`;
                        const fakeEvent = new Event("submit") as unknown as FormEvent;
                        await handleSubmit(fakeEvent, [], fullMessage);
                        setContextText(null);
                        setShowContextBadge(false);
                        setInputValue("");
                        scrollToBottom?.();
                    }, 50);
                    return;
                }
            } else {
                // No prompt provided - show the selected text as a badge above the input
                setContextText(text);
                setShowContextBadge(true);
            }

            // Focus the input
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
        };

        window.addEventListener("follow-up-question", handleFollowUp);
        return () => {
            window.removeEventListener("follow-up-question", handleFollowUp);
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
            const newFiles = Array.from(clipboardData.files).filter(newFile => !selectedFiles.some(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size && existingFile.lastModified === newFile.lastModified));
            if (newFiles.length > 0) {
                setSelectedFiles(prev => [...prev, ...newFiles]);
            }
            return;
        }

        // Handle text pastes - show badge for large text
        const pastedText = clipboardData.getData("text");
        if (pastedText && isLargeText(pastedText)) {
            // Large text - add as pending pasted text badge
            event.preventDefault();
            const newItem = createPastedTextItem(pastedText);
            setPendingPastedTextItems(prev => [...prev, newItem]);
        }
        // Small text pastes go through normally (no preventDefault)
    };

    // Handle saving metadata from the dialog (no upload yet - just stores the configuration)
    const handleSaveMetadata = (metadata: PasteMetadata) => {
        if (!selectedPendingPasteId) return;

        // Update the pending item with the new metadata
        setPendingPastedTextItems(prev =>
            prev.map(item =>
                item.id === selectedPendingPasteId
                    ? {
                          ...item,
                          content: metadata.content,
                          filename: metadata.filename,
                          mimeType: metadata.mimeType,
                          description: metadata.description,
                          isConfigured: true,
                      }
                    : item
            )
        );

        setSelectedPendingPasteId(null);
        setShowArtifactForm(false);
    };

    const handleCancelArtifactForm = () => {
        setSelectedPendingPasteId(null);
        setShowArtifactForm(false);
    };

    const handlePendingPasteClick = (id: string) => {
        setSelectedPendingPasteId(id);
        setShowArtifactForm(true);
    };

    const handleRemovePendingPaste = (id: string) => {
        setPendingPastedTextItems(prev => prev.filter(item => item.id !== id));
    };

    const handleRemoveFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const isSubmittingEnabled = useMemo(() => !isResponding && (inputValue?.trim() || selectedFiles.length !== 0 || pendingPastedTextItems.length !== 0), [isResponding, inputValue, selectedFiles, pendingPastedTextItems]);

    const onSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (isSubmittingEnabled) {
            let fullMessage = inputValue.trim();
            if (contextText && showContextBadge) {
                fullMessage = `Context: "${contextText}"\n\n${fullMessage}`;
            }

            // Upload all pending pasted text items as artifacts, then create references
            interface UploadedArtifact {
                uri: string;
                filename: string;
                mimeType: string;
            }
            const uploadedArtifacts: UploadedArtifact[] = [];
            let effectiveSessionId = sessionId;

            // Build list of existing artifact filenames for uniqueness check
            // Include both session artifacts and any artifacts we've already uploaded in this batch
            const existingFilenames = new Set(artifacts.map(a => a.filename));

            for (let i = 0; i < pendingPastedTextItems.length; i++) {
                const item = pendingPastedTextItems[i];
                try {
                    // Use configured metadata if available, otherwise generate defaults
                    let filename: string;
                    let mimeType: string;
                    let description: string | undefined;

                    if (item.isConfigured && item.filename && item.mimeType) {
                        // User has configured this item via dialog
                        filename = item.filename;
                        mimeType = item.mimeType;
                        description = item.description;
                    } else {
                        // Generate default filename using snippet pattern
                        mimeType = "text/plain";
                        const extension = "txt";
                        filename = `snippet.${extension}`;

                        // Check if filename already exists and generate unique name
                        if (existingFilenames.has(filename)) {
                            let counter = 2;
                            while (existingFilenames.has(`snippet-${counter}.${extension}`)) {
                                counter++;
                            }
                            filename = `snippet-${counter}.${extension}`;
                        }
                    }

                    // Add this filename to the set so subsequent items in this batch get unique names
                    existingFilenames.add(filename);

                    // Create a File object from the text content
                    const blob = new Blob([item.content], { type: mimeType });
                    const file = new File([blob], filename, { type: mimeType });

                    // Upload the artifact via HTTP API (this creates proper metadata)
                    // Pass silent=true to suppress toast notifications for pasted text artifacts
                    const result = await uploadArtifactFile(file, effectiveSessionId, description, true);

                    if (result && !("error" in result)) {
                        // Update effective session ID if a new session was created
                        if (result.sessionId && result.sessionId !== effectiveSessionId) {
                            effectiveSessionId = result.sessionId;
                            setSessionId(result.sessionId);
                        }

                        // Store the uploaded artifact info
                        uploadedArtifacts.push({
                            uri: result.uri,
                            filename: filename,
                            mimeType: mimeType,
                        });
                    } else {
                        const errorDetail = result && "error" in result ? result.error : "An unknown upload error occurred.";
                        throw new Error(errorDetail);
                    }
                } catch (error) {
                    displayError({ title: "Failed to Save Pasted Text", error: getErrorMessage(error) });
                }
            }

            // Create artifact reference files for all uploaded artifacts
            const artifactFiles: File[] = uploadedArtifacts.map(item => {
                // Create a special File object that contains the artifact URI
                const artifactData = JSON.stringify({
                    isArtifactReference: true,
                    uri: item.uri,
                    filename: item.filename,
                    mimeType: item.mimeType,
                });
                const blob = new Blob([artifactData], { type: "application/x-artifact-reference" });
                return new File([blob], item.filename, {
                    type: "application/x-artifact-reference",
                });
            });

            // Combine regular files with artifact references
            const allFiles = [...selectedFiles, ...artifactFiles];

            // Pass the effectiveSessionId to handleSubmit to ensure the message uses the same session
            // as the uploaded artifacts (avoids React state timing issues)
            await handleSubmit(event, allFiles, fullMessage, effectiveSessionId || null);
            setSelectedFiles([]);
            setPendingPastedTextItems([]);
            setInputValue("");
            setContextText(null);
            setShowContextBadge(false);
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

        if (lastChar === "/" && (!charBeforeLast || charBeforeLast === " " || charBeforeLast === "\n")) {
            setShowPromptsCommand(true);
        } else if (showPromptsCommand && !textBeforeCursor.includes("/")) {
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
        const lastSlashIndex = textBeforeCursor.lastIndexOf("/");
        const newText = textBeforeCursor.substring(0, lastSlashIndex) + promptText + textAfterCursor;

        setInputValue(newText);
        setShowPromptsCommand(false);

        // Focus back on input
        setTimeout(() => {
            chatInputRef.current?.focus();
        }, 100);
    };

    // Handle chat command
    const handleChatCommand = (command: ChatCommand, context?: string) => {
        const enhancedMessage = createEnhancedMessage(command, context);

        switch (command) {
            case "create-template": {
                // Navigate to prompts page with AI-assisted mode and pass task description
                navigate("/prompts/new?mode=ai-assisted", {
                    state: { taskDescription: enhancedMessage },
                });

                // Clear input
                setInputValue("");
                setShowPromptsCommand(false);
                break;
            }
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

    // Handle transcription from AudioRecorder
    const handleTranscription = useCallback(
        (text: string) => {
            // Append transcribed text to current input
            const newText = inputValue ? `${inputValue} ${text}` : text;
            setInputValue(newText);

            // Focus the input after transcription
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
        },
        [inputValue]
    );

    // Handle STT errors with persistent banner
    const handleTranscriptionError = useCallback((error: string) => {
        setSttError(error);
    }, []);

    return (
        <div
            className={`bg-card rounded-lg border p-4 shadow-sm ${isDragging ? "border-dotted border-[var(--primary-wMain)] bg-[var(--accent-background)]" : ""}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {/* STT Error Banner */}
            {sttError && (
                <div className="mb-3">
                    <MessageBanner variant="error" message={sttError} dismissible onDismiss={() => setSttError(null)} />
                </div>
            )}

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

            {/* Context Text Badge (from text selection) */}
            {showContextBadge && contextText && (
                <div className="mb-2">
                    <div className="bg-muted/50 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                        <div className="flex flex-1 items-center gap-2">
                            <MessageSquarePlus className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                            <span className="text-muted-foreground max-w-[600px] truncate italic">"{contextText.length > 100 ? contextText.substring(0, 100) + "..." : contextText}"</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="hover:bg-background h-5 w-5 rounded-sm"
                            onClick={() => {
                                setContextText(null);
                                setShowContextBadge(false);
                            }}
                        >
                            <span className="sr-only">Remove context</span>
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                            </svg>
                        </Button>
                    </div>
                </div>
            )}

            {/* Pending Pasted Text Items (not yet uploaded as artifacts) */}
            {pendingPastedTextItems.length > 0 && (
                <div className="mb-2 flex max-h-32 flex-wrap gap-2 overflow-y-auto pt-2 pl-2">
                    {pendingPastedTextItems.map((item, index) => {
                        // Compute default filename for non-configured items
                        // This mirrors the logic used at submit time
                        let defaultFilename = "snippet.txt";
                        if (!item.isConfigured) {
                            const existingFilenames = new Set(artifacts.map(a => a.filename));
                            // Also consider configured items before this one
                            pendingPastedTextItems.slice(0, index).forEach(prevItem => {
                                if (prevItem.isConfigured && prevItem.filename) {
                                    existingFilenames.add(prevItem.filename);
                                }
                            });
                            // Also consider default filenames we've "assigned" to previous non-configured items
                            let tempFilename = "snippet.txt";
                            for (let i = 0; i < index; i++) {
                                const prevItem = pendingPastedTextItems[i];
                                if (!prevItem.isConfigured) {
                                    // This item would get tempFilename
                                    existingFilenames.add(tempFilename);
                                    // Compute next available for the next iteration
                                    if (existingFilenames.has("snippet.txt")) {
                                        let counter = 2;
                                        while (existingFilenames.has(`snippet-${counter}.txt`)) {
                                            counter++;
                                        }
                                        tempFilename = `snippet-${counter}.txt`;
                                    }
                                }
                            }
                            // Now compute the default for this item
                            if (existingFilenames.has("snippet.txt")) {
                                let counter = 2;
                                while (existingFilenames.has(`snippet-${counter}.txt`)) {
                                    counter++;
                                }
                                defaultFilename = `snippet-${counter}.txt`;
                            }
                        }

                        return (
                            <PendingPastedTextBadge
                                key={item.id}
                                id={item.id}
                                content={item.content}
                                onClick={() => handlePendingPasteClick(item.id)}
                                onRemove={() => handleRemovePendingPaste(item.id)}
                                isConfigured={item.isConfigured}
                                filename={item.filename}
                                defaultFilename={defaultFilename}
                            />
                        );
                    })}
                </div>
            )}

            {/* Artifact Configuration Dialog */}
            {(() => {
                const selectedItem = pendingPastedTextItems.find(item => item.id === selectedPendingPasteId);
                const selectedIndex = pendingPastedTextItems.findIndex(item => item.id === selectedPendingPasteId);

                // Build the full list of existing filenames for conflict detection
                // This includes session artifacts AND filenames from other pending items
                const allExistingFilenames = new Set(artifacts.map(a => a.filename));

                // Add filenames from all pending items (except the currently selected one)
                // For configured items, use their configured filename
                // For non-configured items, compute what their default filename would be
                let tempFilename = "snippet.txt";
                pendingPastedTextItems.forEach((item, idx) => {
                    if (item.id === selectedPendingPasteId) {
                        // Skip the currently selected item - we don't want to warn about itself
                        return;
                    }

                    if (item.isConfigured && item.filename) {
                        allExistingFilenames.add(item.filename);
                    } else {
                        // We need to track what filenames have been "assigned" to previous items
                        if (idx < selectedIndex || selectedIndex === -1) {
                            if (allExistingFilenames.has(tempFilename)) {
                                let counter = 2;
                                while (allExistingFilenames.has(`snippet-${counter}.txt`)) {
                                    counter++;
                                }
                                tempFilename = `snippet-${counter}.txt`;
                            }
                            allExistingFilenames.add(tempFilename);
                            // Update tempFilename for next iteration
                            if (allExistingFilenames.has("snippet.txt")) {
                                let counter = 2;
                                while (allExistingFilenames.has(`snippet-${counter}.txt`)) {
                                    counter++;
                                }
                                tempFilename = `snippet-${counter}.txt`;
                            } else {
                                tempFilename = "snippet.txt";
                            }
                        } else {
                            if (allExistingFilenames.has(tempFilename)) {
                                let counter = 2;
                                while (allExistingFilenames.has(`snippet-${counter}.txt`)) {
                                    counter++;
                                }
                                tempFilename = `snippet-${counter}.txt`;
                            }
                            allExistingFilenames.add(tempFilename);
                            // Update tempFilename for next iteration
                            if (allExistingFilenames.has("snippet.txt")) {
                                let counter = 2;
                                while (allExistingFilenames.has(`snippet-${counter}.txt`)) {
                                    counter++;
                                }
                                tempFilename = `snippet-${counter}.txt`;
                            } else {
                                tempFilename = "snippet.txt";
                            }
                        }
                    }
                });

                // Compute default filename for the selected item (same logic as badge display)
                let computedDefaultFilename = "snippet.txt";
                if (selectedItem && !selectedItem.isConfigured && selectedIndex >= 0) {
                    const existingFilenames = new Set(artifacts.map(a => a.filename));
                    // Also consider configured items before this one
                    pendingPastedTextItems.slice(0, selectedIndex).forEach(prevItem => {
                        if (prevItem.isConfigured && prevItem.filename) {
                            existingFilenames.add(prevItem.filename);
                        }
                    });
                    // Also consider default filenames we've "assigned" to previous non-configured items
                    let defaultTempFilename = "snippet.txt";
                    for (let i = 0; i < selectedIndex; i++) {
                        const prevItem = pendingPastedTextItems[i];
                        if (!prevItem.isConfigured) {
                            existingFilenames.add(defaultTempFilename);
                            if (existingFilenames.has("snippet.txt")) {
                                let counter = 2;
                                while (existingFilenames.has(`snippet-${counter}.txt`)) {
                                    counter++;
                                }
                                defaultTempFilename = `snippet-${counter}.txt`;
                            }
                        }
                    }
                    // Now compute the default for this item
                    if (existingFilenames.has("snippet.txt")) {
                        let counter = 2;
                        while (existingFilenames.has(`snippet-${counter}.txt`)) {
                            counter++;
                        }
                        computedDefaultFilename = `snippet-${counter}.txt`;
                    }
                }

                return (
                    <PasteActionDialog
                        isOpen={showArtifactForm}
                        content={selectedItem?.content || ""}
                        onSaveMetadata={handleSaveMetadata}
                        onCancel={handleCancelArtifactForm}
                        existingArtifacts={Array.from(allExistingFilenames)}
                        initialFilename={selectedItem?.filename}
                        initialMimeType={selectedItem?.mimeType}
                        initialDescription={selectedItem?.description}
                        defaultFilename={computedDefaultFilename}
                    />
                );
            })()}

            {/* Prompts Command Popover */}
            <PromptsCommand
                isOpen={showPromptsCommand}
                onClose={() => {
                    setShowPromptsCommand(false);
                }}
                textAreaRef={chatInputRef}
                onPromptSelect={handlePromptSelect}
                messages={messages}
                onReservedCommand={handleChatCommand}
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
                placeholder={isRecording ? "Recording..." : "How can I help you today? (Type '/' to insert a prompt)"}
                className="field-sizing-content max-h-50 min-h-0 resize-none rounded-2xl border-none p-3 text-base/normal shadow-none transition-[height] duration-500 ease-in-out focus-visible:outline-none"
                rows={1}
                onPaste={handlePaste}
                disabled={isRecording}
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

                {/* Spacer to push buttons to the right */}
                <div className="flex-1" />

                {/* Microphone button - show if STT feature enabled and STT setting enabled */}
                {sttEnabled && settings.speechToText && <AudioRecorder disabled={isResponding} onTranscriptionComplete={handleTranscription} onError={handleTranscriptionError} onRecordingStateChange={setIsRecording} />}

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
