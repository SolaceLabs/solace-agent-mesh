import React, { useRef, useState, useEffect, useMemo, useCallback } from "react";
import type { ChangeEvent, FormEvent, ClipboardEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import { Ban, Paperclip, Send, MessageSquarePlus, Lightbulb, MessageSquare, X } from "lucide-react";

import { Button, ChatInput, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Popover, PopoverContent, PopoverTrigger, ScrollArea, Switch } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { useChatContext, useDragAndDrop, useAgentSelection, useAudioSettings, useConfigContext } from "@/lib/hooks";
import type { AgentCardInfo, Skill } from "@/lib/types";
import type { PromptGroup } from "@/lib/types/prompts";
import { detectVariables } from "@/lib/utils/promptUtils";

import { FileBadge } from "./file/FileBadge";
import { AudioRecorder } from "./AudioRecorder";
import { PromptsCommand, type ChatCommand } from "./PromptsCommand";
import { VariableDialog } from "./VariableDialog";
import { PastedTextBadge, PasteActionDialog, isLargeText, type PastedArtifactItem } from "./paste";

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
    const { isResponding, isCancelling, selectedAgentName, sessionId, setSessionId, handleSubmit, handleCancel, uploadArtifactFile, artifactsRefetch, addNotification, artifacts, setPreviewArtifact, openSidePanelTab, messages } = useChatContext();
    const { handleAgentSelection } = useAgentSelection();
    const { settings } = useAudioSettings();
    const { configFeatureEnablement } = useConfigContext();

    // Feature flags
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;

    // File selection support
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

    // Pasted artifact support
    const [pastedArtifactItems, setPastedArtifactItems] = useState<PastedArtifactItem[]>([]);
    const [pendingPasteContent, setPendingPasteContent] = useState<string | null>(null);
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

    // Track active skills for context (multiple skills can be selected)
    const [activeSkills, setActiveSkills] = useState<Map<string, { id: string; name: string; description: string; markdownContent?: string }>>(new Map());

    // Track which skills have already been injected in the current session
    // Once a skill is injected, it's in the conversation history and doesn't need to be re-sent
    const [injectedSkillIds, setInjectedSkillIds] = useState<Set<string>>(new Set());

    // Skills dropdown state
    const [showSkillsDropdown, setShowSkillsDropdown] = useState(false);
    const [availableSkills, setAvailableSkills] = useState<Skill[]>([]);
    const [skillsLoading, setSkillsLoading] = useState(false);

    // Legacy single skill support (for backward compatibility with "Use in Chat" from Skills page)
    const [activeSkill, setActiveSkill] = useState<{ id: string; name: string; description: string; markdownContent?: string } | null>(null);

    // Fetch full skill content when skill is activated
    const fetchSkillContent = async (skillId: string) => {
        try {
            const { authenticatedFetch: authFetch } = await import("@/lib/utils/api");
            const response = await authFetch(`/api/v1/skills/${skillId}`, {
                credentials: "include",
            });
            if (response.ok) {
                const data = await response.json();
                return data.markdown_content || data.markdownContent;
            }
        } catch (error) {
            console.error("Failed to fetch skill content:", error);
        }
        return null;
    };

    // Fetch available skills for the dropdown
    const fetchAvailableSkills = async () => {
        setSkillsLoading(true);
        try {
            const { authenticatedFetch: authFetch } = await import("@/lib/utils/api");
            const params = new URLSearchParams();
            if (selectedAgentName) {
                params.append("agent", selectedAgentName);
            }

            const response = await authFetch(`/api/v1/skills?${params.toString()}`, {
                credentials: "include",
            });
            if (response.ok) {
                const data = await response.json();
                // Map snake_case API response to camelCase frontend types
                const mappedSkills = (data.skills || []).map((s: Record<string, unknown>) => ({
                    id: s.id as string,
                    name: s.name as string,
                    description: s.description as string,
                    type: s.type as string,
                    scope: s.scope as string,
                    ownerAgent: s.owner_agent as string | undefined,
                    tags: (s.tags as string[]) || [],
                    successRate: s.success_rate as number | undefined,
                    usageCount: (s.usage_count as number) || 0,
                    isActive: (s.is_active as boolean) ?? true,
                }));
                setAvailableSkills(mappedSkills);
            }
        } catch (error) {
            console.error("Failed to fetch skills:", error);
        } finally {
            setSkillsLoading(false);
        }
    };

    // Toggle skill selection
    const toggleSkill = async (skill: Skill) => {
        const newActiveSkills = new Map(activeSkills);

        if (newActiveSkills.has(skill.id)) {
            newActiveSkills.delete(skill.id);
        } else {
            // Fetch full content for the skill
            const markdownContent = await fetchSkillContent(skill.id);
            newActiveSkills.set(skill.id, {
                id: skill.id,
                name: skill.name,
                description: skill.description,
                markdownContent: markdownContent || undefined,
            });
        }

        setActiveSkills(newActiveSkills);
    };

    // Clear all selected skills
    const clearAllSkills = () => {
        setActiveSkills(new Map());
        setActiveSkill(null);
    };

    useEffect(() => {
        // Check for pending prompt use from router state
        if (location.state?.promptText) {
            const { promptText, groupId, groupName } = location.state;

            // Check if prompt has variables
            const variables = detectVariables(promptText);
            if (variables.length > 0) {
                // Show variable dialog
                setPendingPromptGroup({
                    id: groupId,
                    name: groupName,
                    productionPrompt: { promptText: promptText },
                } as PromptGroup);
                setShowVariableDialog(true);
            } else {
                setInputValue(promptText);
                setTimeout(() => {
                    chatInputRef.current?.focus();
                }, 100);
            }

            // Clear the location state to prevent re-triggering
            navigate(location.pathname, { replace: true, state: {} });
            return; // Don't clear input if we just set it
        }

        // Check for skill use from router state
        if (location.state?.skillId) {
            const { skillId, skillName, skillDescription } = location.state;

            // Fetch full skill content
            fetchSkillContent(skillId).then(markdownContent => {
                setActiveSkill({
                    id: skillId,
                    name: skillName,
                    description: skillDescription,
                    markdownContent: markdownContent || undefined,
                });
            });

            // Clear the location state to prevent re-triggering
            navigate(location.pathname, { replace: true, state: {} });

            // Focus the input
            setTimeout(() => {
                chatInputRef.current?.focus();
            }, 100);
            return;
        }

        // Only clear if session actually changed (not just initialized)
        if (prevSessionIdRef.current && prevSessionIdRef.current !== sessionId) {
            setInputValue("");
            setShowPromptsCommand(false);
            setPastedArtifactItems([]);
            setActiveSkill(null);
            setActiveSkills(new Map());
            // Clear injected skills tracking when session changes
            setInjectedSkillIds(new Set());
        }
        prevSessionIdRef.current = sessionId;
        setContextText(null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId, location.state?.skillId, location.state?.promptText, location.state?.timestamp, location.pathname, navigate]);

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

        // Handle text pastes - show artifact form for large text
        const pastedText = clipboardData.getData("text");
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
            let mimeType = "text/plain";
            if (fileType !== "auto") {
                mimeType = fileType;
            }

            // Create a File object from the text content
            const blob = new Blob([pendingPasteContent], { type: mimeType });
            const file = new File([blob], title, { type: mimeType });

            // Upload the artifact
            const result = await uploadArtifactFile(file, sessionId, description);

            if (result) {
                // Type guard: check if result is an error
                if ("error" in result) {
                    addNotification(`Failed to create artifact: ${result.error}`, "error");
                    return;
                }

                // Now TypeScript knows result has uri and sessionId
                // If a new session was created, update our sessionId
                if (result.sessionId && result.sessionId !== sessionId) {
                    setSessionId(result.sessionId);
                }

                // Create a badge item for this pasted artifact
                const artifactItem: PastedArtifactItem = {
                    id: `paste-artifact-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                    artifactId: result.uri,
                    filename: title,
                    mimeType: mimeType,
                    timestamp: Date.now(),
                };
                setPastedArtifactItems(prev => {
                    return [...prev, artifactItem];
                });

                addNotification(`Artifact "${title}" created from pasted content.`);
                // Refresh artifacts panel
                await artifactsRefetch();
            } else {
                addNotification(`Failed to create artifact from pasted content.`, "error");
            }
        } catch (error) {
            console.error("Error saving artifact:", error);
            addNotification(`Error creating artifact: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
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

    const isSubmittingEnabled = useMemo(() => !isResponding && (inputValue?.trim() || selectedFiles.length !== 0 || pastedArtifactItems.length !== 0), [isResponding, inputValue, selectedFiles, pastedArtifactItems]);

    const onSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (isSubmittingEnabled) {
            let fullMessage = inputValue.trim();
            if (contextText && showContextBadge) {
                fullMessage = `Context: "${contextText}"\n\n${fullMessage}`;
            }

            // Note: skill_id is passed via metadata to the backend, which injects skill content into the message
            // Once injected, the skill context is in the conversation history and doesn't need to be re-sent
            // We only send skill_id for NEW skills that haven't been injected yet in this session

            // Combine legacy single skill with multi-select skills
            const allActiveSkillIds: string[] = [];
            if (activeSkill?.id) {
                allActiveSkillIds.push(activeSkill.id);
            }
            activeSkills.forEach((_, skillId) => {
                if (!allActiveSkillIds.includes(skillId)) {
                    allActiveSkillIds.push(skillId);
                }
            });

            // Filter to only skills that haven't been injected yet
            const newSkillIds = allActiveSkillIds.filter(id => !injectedSkillIds.has(id));

            // Mark all active skills as injected after this message
            // (they'll be in the conversation history)
            if (allActiveSkillIds.length > 0) {
                setInjectedSkillIds(prev => {
                    const newSet = new Set(prev);
                    allActiveSkillIds.forEach(id => newSet.add(id));
                    return newSet;
                });
            }

            const artifactFiles: File[] = pastedArtifactItems
                .filter(item => item.artifactId && item.mimeType) // Skip invalid items early
                .map(item => {
                    // Create a special File object that contains the artifact URI
                    const artifactData = JSON.stringify({
                        isArtifactReference: true,
                        uri: item.artifactId,
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

            await handleSubmit(event, allFiles, fullMessage, { skillIds: newSkillIds.length > 0 ? newSkillIds : undefined });
            setSelectedFiles([]);
            setPastedArtifactItems([]);
            setInputValue("");
            setContextText(null);
            setShowContextBadge(false);
            // Note: Skills are NOT cleared after submission - they persist for follow-up messages
            // Users can manually clear skills using the X button on badges or "Clear all" button
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
            openSidePanelTab("files");
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
            className={`rounded-lg border p-4 shadow-sm ${isDragging ? "border-dotted border-[var(--primary-wMain)] bg-[var(--accent-background)]" : ""}`}
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

            {/* Active Skills Badges */}
            {(activeSkill || activeSkills.size > 0) && (
                <div className="mb-2 flex flex-wrap gap-2">
                    {/* Legacy single skill badge */}
                    {activeSkill && !activeSkills.has(activeSkill.id) && (
                        <div className="bg-primary/10 border-primary/20 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                            <div className="flex flex-1 items-center gap-2">
                                <MessageSquare className="text-primary h-4 w-4" />
                                <span className="text-primary font-medium">{activeSkill.name}</span>
                            </div>
                            <Button variant="ghost" size="icon" className="hover:bg-background h-5 w-5 rounded-sm" onClick={() => setActiveSkill(null)}>
                                <span className="sr-only">Remove skill</span>
                                <X className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    )}
                    {/* Multi-select skill badges */}
                    {Array.from(activeSkills.values()).map(skill => (
                        <div key={skill.id} className="bg-primary/10 border-primary/20 inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                            <div className="flex flex-1 items-center gap-2">
                                <MessageSquare className="text-primary h-4 w-4" />
                                <span className="text-primary font-medium">{skill.name}</span>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="hover:bg-background h-5 w-5 rounded-sm"
                                onClick={() => {
                                    const newSkills = new Map(activeSkills);
                                    newSkills.delete(skill.id);
                                    setActiveSkills(newSkills);
                                }}
                            >
                                <span className="sr-only">Remove skill</span>
                                <X className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    ))}
                    {/* Clear all button when multiple skills */}
                    {(activeSkills.size > 1 || (activeSkill && activeSkills.size > 0)) && (
                        <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground h-auto px-2 py-1 text-xs" onClick={clearAllSkills}>
                            Clear all
                        </Button>
                    )}
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

            {/* Pasted Artifact Items */}
            {(() => {
                return (
                    pastedArtifactItems.length > 0 && (
                        <div className="mb-2 flex flex-wrap gap-2">
                            {pastedArtifactItems.map((item, index) => (
                                <PastedTextBadge key={item.id} id={item.id} index={index + 1} textPreview={item.filename} onClick={() => handleViewPastedArtifact(item.filename)} onRemove={() => handleRemovePastedArtifact(item.id)} />
                            ))}
                        </div>
                    )
                );
            })()}

            {/* Artifact Creation Dialog */}
            <PasteActionDialog isOpen={showArtifactForm} content={pendingPasteContent || ""} onSaveAsArtifact={handleSaveAsArtifact} onCancel={handleCancelArtifactForm} existingArtifacts={artifacts.map(a => a.filename)} />

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

                {/* Skills Button with Dropdown */}
                <Popover
                    open={showSkillsDropdown}
                    onOpenChange={open => {
                        setShowSkillsDropdown(open);
                        if (open) {
                            fetchAvailableSkills();
                        }
                    }}
                >
                    <PopoverTrigger asChild>
                        <Button variant="ghost" disabled={isResponding} tooltip="Attach skills" className={activeSkills.size > 0 || activeSkill ? "text-primary" : ""}>
                            <Lightbulb className="size-4" />
                            {(activeSkills.size > 0 || activeSkill) && (
                                <span className="bg-primary text-primary-foreground ml-1 flex h-4 w-4 items-center justify-center rounded-full text-xs">{activeSkills.size + (activeSkill && !activeSkills.has(activeSkill.id) ? 1 : 0)}</span>
                            )}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80 p-0" align="start" sideOffset={5}>
                        <div className="flex max-h-80 flex-col overflow-hidden">
                            <ScrollArea className="flex-1">
                                <div className="p-2">
                                    {skillsLoading ? (
                                        <div className="text-muted-foreground flex items-center justify-center py-4 text-sm">Loading skills...</div>
                                    ) : availableSkills.length === 0 ? (
                                        <div className="text-muted-foreground flex items-center justify-center py-4 text-sm">No skills available</div>
                                    ) : (
                                        <>
                                            {/* Group skills by scope */}
                                            {(() => {
                                                const globalSkills = availableSkills.filter(s => s.scope === "global");
                                                // Only show agent skills that belong to the currently selected agent
                                                const agentSkills = availableSkills.filter(s => s.scope === "agent" && s.ownerAgent && selectedAgentName && s.ownerAgent === selectedAgentName);
                                                const userSkills = availableSkills.filter(s => s.scope === "user" || s.scope === "shared");

                                                return (
                                                    <>
                                                        {globalSkills.length > 0 && (
                                                            <div className="mb-2">
                                                                <div className="text-muted-foreground mb-1 px-2 text-xs font-medium uppercase">Global Skills</div>
                                                                {globalSkills.map(skill => (
                                                                    <div key={skill.id} className="hover:bg-accent flex w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-sm">
                                                                        <div className="truncate font-medium">{skill.name}</div>
                                                                        <Switch checked={activeSkills.has(skill.id)} onCheckedChange={() => toggleSkill(skill)} />
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                        {agentSkills.length > 0 && (
                                                            <div className="mb-2">
                                                                <div className="text-muted-foreground mb-1 px-2 text-xs font-medium uppercase">Agent Skills</div>
                                                                {agentSkills.map(skill => (
                                                                    <div key={skill.id} className="hover:bg-accent flex w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-sm">
                                                                        <div className="truncate font-medium">{skill.name}</div>
                                                                        <Switch checked={activeSkills.has(skill.id)} onCheckedChange={() => toggleSkill(skill)} />
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                        {userSkills.length > 0 && (
                                                            <div className="mb-2">
                                                                <div className="text-muted-foreground mb-1 px-2 text-xs font-medium uppercase">My Skills</div>
                                                                {userSkills.map(skill => (
                                                                    <div key={skill.id} className="hover:bg-accent flex w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-sm">
                                                                        <div className="truncate font-medium">{skill.name}</div>
                                                                        <Switch checked={activeSkills.has(skill.id)} onCheckedChange={() => toggleSkill(skill)} />
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </>
                                                );
                                            })()}
                                        </>
                                    )}
                                </div>
                            </ScrollArea>
                            {activeSkills.size > 0 && (
                                <div className="flex-shrink-0 border-t p-2">
                                    <Button variant="ghost" size="sm" className="w-full" onClick={clearAllSkills}>
                                        Clear all ({activeSkills.size})
                                    </Button>
                                </div>
                            )}
                        </div>
                    </PopoverContent>
                </Popover>

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
