import React, { useRef, useState, useEffect, useMemo, useCallback } from "react";
import type { ChangeEvent, FormEvent, ClipboardEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import { Ban, Paperclip, Send, MessageSquarePlus, X } from "lucide-react";

import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { MentionContentEditable } from "@/lib/components/ui/chat/MentionContentEditable";
import { useChatContext, useDragAndDrop, useAgentSelection, useAudioSettings, useConfigContext } from "@/lib/hooks";
import type { AgentCardInfo, Person } from "@/lib/types";
import type { PromptGroup } from "@/lib/types/prompts";
import { detectVariables } from "@/lib/utils/promptUtils";
import { detectMentionTrigger, insertMention, buildMessageFromDOM } from "@/lib/utils/mentionUtils";
import { addRecentMention } from "@/lib/utils/recentMentions";

import { FileBadge } from "./file/FileBadge";
import { AudioRecorder } from "./AudioRecorder";
import { PromptsCommand, type ChatCommand } from "./PromptsCommand";
import { MentionsCommand } from "./MentionsCommand";
import { VariableDialog } from "./VariableDialog";
import { PendingPastedTextBadge, PasteActionDialog, isLargeText, createPastedTextItem, type PasteMetadata, type PastedTextItem } from "./paste";
import { getErrorMessage, escapeMarkdown } from "@/lib/utils";

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
    const mentionsEnabled = configFeatureEnablement?.mentions ?? false;

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

    const chatInputRef = useRef<HTMLDivElement>(null);
    const prevIsRespondingRef = useRef<boolean>(isResponding);

    const [inputValue, setInputValue] = useState<string>("");
    const [desiredCursorPosition, setDesiredCursorPosition] = useState<number | undefined>(undefined);

    const [showPromptsCommand, setShowPromptsCommand] = useState(false);
    const [showMentionsCommand, setShowMentionsCommand] = useState(false);
    const [mentionSearchQuery, setMentionSearchQuery] = useState("");
    // mentionMap is keyed by person.id for unique identification
    const [mentionMap, setMentionMap] = useState<Map<string, Person>>(new Map());
    // Track which person IDs need disambiguation (when multiple people share the same name)
    const [disambiguatedIds, setDisambiguatedIds] = useState<Set<string>>(new Set());

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
                        const fullMessage = `${prompt}\n\nContext: "${escapeMarkdown(text)}"`;
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

    const handlePaste = async (event: ClipboardEvent<Element>) => {
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
            let fullMessage = chatInputRef.current ? buildMessageFromDOM(chatInputRef.current).trim() : inputValue.trim();

            // Capture the display HTML for showing in user's message bubble
            const displayHtml = chatInputRef.current?.innerHTML || null;

            if (contextText && showContextBadge) {
                fullMessage = `Context: "${escapeMarkdown(contextText)}"\n\n${fullMessage}`;
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
            await handleSubmit(event, allFiles, fullMessage, effectiveSessionId || null, displayHtml);
            setSelectedFiles([]);
            setPendingPastedTextItems([]);
            setInputValue("");
            setMentionMap(new Map()); // Clear mention map after submit
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

    // Get cursor position in terms of internal format length
    // This accounts for mention chips which have different display vs internal lengths
    const getCursorPosition = (): number => {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) return 0;
        if (!chatInputRef.current) return 0;

        const range = selection.getRangeAt(0);
        let position = 0;
        let found = false;

        // Walk through all nodes to calculate position in internal format
        const walker = document.createTreeWalker(chatInputRef.current, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
            acceptNode: (node: Node) => {
                // Skip text nodes inside mention chips (we handle the chip as a whole)
                if (node.nodeType === Node.TEXT_NODE) {
                    const parent = node.parentElement;
                    if (parent && parent.classList.contains("mention-chip")) {
                        return NodeFilter.FILTER_REJECT;
                    }
                }
                return NodeFilter.FILTER_ACCEPT;
            },
        });

        let node: Node | null;
        while ((node = walker.nextNode()) && !found) {
            if (node.nodeType === Node.TEXT_NODE) {
                if (node === range.startContainer) {
                    position += range.startOffset;
                    found = true;
                } else {
                    position += node.textContent?.length || 0;
                }
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                const el = node as HTMLElement;
                if (el.classList.contains("mention-chip")) {
                    // Add full internal format length
                    const internal = el.getAttribute("data-internal") || "";
                    position += internal.length;
                    // Check if cursor is inside this chip
                    if (range.startContainer === el || el.contains(range.startContainer)) {
                        found = true;
                    }
                } else if (el.tagName === "BR") {
                    position += 1; // Newline
                }
            }
        }

        return position;
    };

    // Handle input change with "/" and "@" detection
    const handleInputChange = (value: string) => {
        setInputValue(value);

        const cursorPosition = getCursorPosition();
        const textBeforeCursor = value.substring(0, cursorPosition);

        // Check if "/" is typed as the first character (position 0)
        // Only trigger prompt popover when "/" is at the very start of the input
        if (textBeforeCursor === "/") {
            setShowPromptsCommand(true);
            setShowMentionsCommand(false); // Close mentions if open
        } else if (showPromptsCommand && !textBeforeCursor.startsWith("/")) {
            setShowPromptsCommand(false);
        }

        // Check for "@" mention trigger
        if (mentionsEnabled) {
            const mentionQuery = detectMentionTrigger(value, cursorPosition);
            if (mentionQuery !== null) {
                setMentionSearchQuery(mentionQuery);
                setShowMentionsCommand(true);
                setShowPromptsCommand(false); // Close prompts if open
            } else if (showMentionsCommand) {
                setShowMentionsCommand(false);
                setMentionSearchQuery("");
            }
        }
    };

    // Handle prompt selection
    const handlePromptSelect = (promptText: string) => {
        // Remove the "/" trigger and insert the prompt
        const cursorPosition = getCursorPosition();
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

    // Handle person selection for mentions
    const handlePersonSelect = (person: Person) => {
        const cursorPosition = getCursorPosition();

        // Insert the mention using internal format @[Name](id)
        const { newText, newCursorPosition } = insertMention(inputValue, cursorPosition, person);

        // Check if there's already a person with the same name but different ID
        // If so, both need disambiguation
        let needsDisambiguation = false;
        let existingPersonId: string | undefined;

        for (const [id, existingPerson] of mentionMap.entries()) {
            if (existingPerson.displayName === person.displayName && id !== person.id) {
                needsDisambiguation = true;
                existingPersonId = id;
                break;
            }
        }

        // Update mentionMap (keyed by ID)
        setMentionMap(prev => {
            const updated = new Map(prev);
            updated.set(person.id, person);
            return updated;
        });

        // Update disambiguation tracking
        if (needsDisambiguation && existingPersonId) {
            setDisambiguatedIds(prev => {
                const updated = new Set(prev);
                updated.add(existingPersonId!);
                updated.add(person.id);
                return updated;
            });
        }

        // Add to recent mentions
        addRecentMention(person);

        setInputValue(newText);
        setDesiredCursorPosition(newCursorPosition); // Set cursor after the mention
        setShowMentionsCommand(false);
        setMentionSearchQuery("");

        // Clear cursor position state after it's been applied - bit of a hack, but really struggled to make this work
        setTimeout(() => {
            setDesiredCursorPosition(undefined);
        }, 10);
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
                <div className="mb-2 overflow-hidden">
                    <div className="bg-muted/50 inline-flex max-w-full items-center gap-2 overflow-hidden rounded-md border px-3 py-2 text-sm">
                        <MessageSquarePlus className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                        <span className="text-muted-foreground min-w-0 flex-1 truncate italic">"{contextText}"</span>
                        <Button
                            variant="ghost"
                            className="h-5 w-5 shrink-0"
                            onClick={() => {
                                setContextText(null);
                                setShowContextBadge(false);
                            }}
                            tooltip="Remove context"
                        >
                            <X />
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
                onBackspaceClose={() => {
                    // Remove the "/" trigger character from the input
                    // Since "/" only triggers at position 0, we just remove the first character
                    if (inputValue.startsWith("/")) {
                        setInputValue(inputValue.substring(1));
                    }
                    setShowPromptsCommand(false);
                }}
            />

            {/* Mentions Command Popover */}
            {mentionsEnabled && (
                <MentionsCommand
                    isOpen={showMentionsCommand}
                    onClose={() => {
                        setShowMentionsCommand(false);
                        setMentionSearchQuery("");
                    }}
                    textAreaRef={chatInputRef}
                    onPersonSelect={handlePersonSelect}
                    searchQuery={mentionSearchQuery}
                />
            )}

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

            {/* Chat Input with Mention Chips */}
            <MentionContentEditable
                ref={chatInputRef}
                value={inputValue}
                onChange={handleInputChange}
                cursorPosition={desiredCursorPosition}
                mentionMap={mentionMap}
                disambiguatedIds={disambiguatedIds}
                placeholder={isRecording ? "Recording..." : mentionsEnabled ? "How can I help you today? (Type '/' to insert a prompt, '@' to mention someone)" : "How can I help you today? (Type '/' to insert a prompt)"}
                className="field-sizing-content max-h-50 min-h-0 resize-none rounded-2xl border-none p-3 text-base/normal shadow-none focus-visible:outline-none"
                onPaste={handlePaste}
                disabled={isRecording}
                onKeyDown={event => {
                    // Don't handle Enter if mentions or prompts popup is open
                    if (showMentionsCommand || showPromptsCommand) {
                        return;
                    }

                    if (event.key === "Enter" && !event.shiftKey && isSubmittingEnabled) {
                        onSubmit(event);
                    }
                }}
            />

            {/* Buttons */}
            <div className="relative m-2 flex items-center gap-2">
                <Button variant="ghost" onClick={handleFileSelect} disabled={isResponding} tooltip="Attach file">
                    <Paperclip className="size-4" />
                </Button>

                <div>Agent: </div>
                <Select
                    value={selectedAgentName}
                    onValueChange={agentName => {
                        handleAgentSelection(agentName);
                    }}
                    disabled={isResponding || agents.length === 0}
                >
                    <SelectTrigger className="w-[250px]">
                        <SelectValue placeholder="Select an agent..." />
                    </SelectTrigger>
                    <SelectContent>
                        {agents
                            .filter(agent => !agent.isWorkflow)
                            .map(agent => (
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
                    <Button data-testid="cancel" className="ml-auto gap-1.5" onClick={handleCancel} variant="outline" disabled={isCancelling}>
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
