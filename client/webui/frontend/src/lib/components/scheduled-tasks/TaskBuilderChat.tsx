import React, { useState, useEffect, useRef, useCallback } from "react";
import { Send, Loader2, Sparkles } from "lucide-react";
import { AudioRecorder, Button, MarkdownWrapper, MessageBanner, Textarea } from "@/lib/components";
import { useAudioSettings, useConfigContext, useChatContext } from "@/lib/hooks";
import { api } from "@/lib/api/client";
import { useQuery, useMutation } from "@tanstack/react-query";
import { AgentPickerCard, type AgentPickerSuggestion } from "./AgentPickerCard";
import { cn } from "@/lib/utils";

interface InlineAgentPicker {
    type: "agent_picker";
    prompt: string;
    suggestions: AgentPickerSuggestion[];
    allowOther: boolean;
}

interface Message {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
    inlineComponent?: InlineAgentPicker;
    resolvedAgentName?: string;
}

interface ChatResponse {
    message: string;
    taskUpdates: Record<string, unknown>;
    confidence: number;
    readyToSave: boolean;
    inlineComponent?: InlineAgentPicker;
}

interface ApiInlineComponent {
    type: string;
    prompt?: string;
    suggestions?: Array<{ name: string; reason?: string }>;
    allow_other?: boolean;
}

interface ApiChatResponse {
    message: string;
    task_updates: Record<string, unknown>;
    confidence: number;
    ready_to_save: boolean;
    inline_component?: ApiInlineComponent | null;
}

function transformChatResponse(apiResponse: ApiChatResponse): ChatResponse {
    let inlineComponent: InlineAgentPicker | undefined;
    const raw = apiResponse.inline_component;
    if (raw && raw.type === "agent_picker" && Array.isArray(raw.suggestions) && raw.suggestions.length > 0) {
        inlineComponent = {
            type: "agent_picker",
            prompt: raw.prompt || "What agent would you like to use?",
            suggestions: raw.suggestions.map(s => ({ name: s.name, reason: s.reason ?? "" })),
            allowOther: raw.allow_other ?? true,
        };
    }
    return {
        message: apiResponse.message,
        taskUpdates: apiResponse.task_updates,
        confidence: apiResponse.confidence,
        readyToSave: apiResponse.ready_to_save,
        inlineComponent,
    };
}

interface TaskConfig {
    name?: string;
    description?: string;
    scheduleType?: string;
    scheduleExpression?: string;
    targetAgentName?: string;
    taskMessage?: string;
    timezone?: string;
}

interface TaskBuilderChatProps {
    onConfigUpdate: (config: Partial<TaskConfig>) => void;
    currentConfig: TaskConfig;
    onReadyToSave: (ready: boolean) => void;
    initialMessage?: string | null;
    availableAgents?: Array<{ name: string; displayName?: string; description?: string }>;
    isEditing?: boolean;
}

export const TaskBuilderChat: React.FC<TaskBuilderChatProps> = ({ onConfigUpdate, currentConfig, onReadyToSave, initialMessage, availableAgents = [], isEditing = false }) => {
    const { addNotification } = useChatContext();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [hasUserMessage, setHasUserMessage] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const initRef = useRef(false);
    const currentConfigRef = useRef(currentConfig);
    currentConfigRef.current = currentConfig;
    const availableAgentsRef = useRef(availableAgents);
    availableAgentsRef.current = availableAgents;

    // Speech-to-text support
    const { settings } = useAudioSettings();
    const { configFeatureEnablement } = useConfigContext();
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;
    const [sttError, setSttError] = useState<string | null>(null);
    const [isRecording, setIsRecording] = useState(false);

    // Fetch greeting via React Query (handles unmount lifecycle)
    const greetingQuery = useQuery({
        queryKey: ["scheduled-tasks", "builder", "greeting"],
        queryFn: () => api.webui.get("/api/v1/scheduled-tasks/builder/greeting") as Promise<{ message: string }>,
        staleTime: Infinity,
        refetchOnMount: false,
    });

    // Chat mutation via React Query (handles unmount lifecycle)
    const chatMutation = useMutation({
        mutationFn: (payload: { message: string; conversation_history: Array<{ role: string; content: string }>; current_task: TaskConfig; available_agents: Array<{ name: string; display_name?: string; description?: string }> }) =>
            api.webui.post("/api/v1/scheduled-tasks/builder/chat", payload) as Promise<ApiChatResponse>,
    });

    const buildAvailableAgentsPayload = useCallback(
        () =>
            availableAgentsRef.current.map(a => ({
                name: a.name,
                ...(a.displayName ? { display_name: a.displayName } : {}),
                ...(a.description ? { description: a.description } : {}),
            })),
        []
    );

    // Auto-scroll to bottom when new messages arrive
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Initialize chat with greeting and optionally send initial message
    useEffect(() => {
        if (initRef.current || !greetingQuery.data) return;
        initRef.current = true;

        // In edit mode the backend greeting ("Hi! I'll help you create a
        // scheduled task...") doesn't fit — the user already has a task and
        // is here to change it. Swap in a context-aware greeting that
        // references the existing task's name if we have one.
        const taskName = currentConfigRef.current?.name?.trim();
        const greetingMessage = isEditing
            ? `Hi! Let's refine${taskName ? ` the **${taskName}**` : " this"} task. Tell me what you'd like to change — for example the schedule, target agent, or the instructions. I can also help tweak the wording.`
            : greetingQuery.data.message;
        setMessages([
            {
                role: "assistant",
                content: greetingMessage,
                timestamp: new Date(),
            },
        ]);

        // If there's an initial message, send it automatically
        if (initialMessage) {
            setHasUserMessage(true);
            const userMessage: Message = {
                role: "user",
                content: initialMessage,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, userMessage]);
            setTimeout(() => scrollToBottom(), 100);

            chatMutation.mutate(
                {
                    message: initialMessage,
                    conversation_history: [{ role: "assistant", content: greetingMessage }],
                    current_task: currentConfigRef.current,
                    available_agents: buildAvailableAgentsPayload(),
                },
                {
                    onSuccess: apiData => {
                        const chatData = transformChatResponse(apiData);
                        setMessages(prev => [...prev, { role: "assistant", content: chatData.message, timestamp: new Date(), inlineComponent: chatData.inlineComponent }]);
                        if (Object.keys(chatData.taskUpdates).length > 0) {
                            onConfigUpdate(chatData.taskUpdates);
                        }
                        onReadyToSave(chatData.readyToSave);
                        setTimeout(() => scrollToBottom(), 100);
                    },
                    onError: error => {
                        addNotification(error instanceof Error ? error.message : "Failed to process initial message", "warning");
                        setMessages(prev => [...prev, { role: "assistant", content: "I encountered an error processing your request. Please try describing your task manually.", timestamp: new Date() }]);
                    },
                }
            );
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [greetingQuery.data]);

    // Handle greeting fetch error
    useEffect(() => {
        if (greetingQuery.error && !initRef.current) {
            initRef.current = true;
            addNotification(greetingQuery.error instanceof Error ? greetingQuery.error.message : "Failed to initialize chat", "warning");
            setMessages([
                {
                    role: "assistant",
                    content: "Hi! I'll help you create a scheduled task. What would you like to automate?",
                    timestamp: new Date(),
                },
            ]);
        }
    }, [greetingQuery.error, addNotification]);

    // Auto-focus input when component mounts and is not loading
    const isInitializing = greetingQuery.isLoading;
    const isLoading = chatMutation.isPending;

    useEffect(() => {
        if (!isInitializing && !isLoading && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isInitializing, isLoading]);

    // Auto-resize textarea based on content
    useEffect(() => {
        const textarea = inputRef.current;
        if (!textarea) return;

        const adjustHeight = () => {
            textarea.style.height = "auto";
            const newHeight = Math.min(textarea.scrollHeight, 200);
            textarea.style.height = `${newHeight}px`;
        };

        adjustHeight();
    }, [input]);

    // Handle transcription from AudioRecorder
    const handleTranscription = useCallback(
        (text: string) => {
            const newText = input ? `${input} ${text}` : text;
            setInput(newText);
            setTimeout(() => {
                inputRef.current?.focus();
            }, 100);
        },
        [input]
    );

    // Handle STT errors with persistent banner
    const handleTranscriptionError = useCallback((error: string) => {
        setSttError(error);
    }, []);

    const sendMessage = (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || isLoading) return;

        const userMessage: Message = {
            role: "user",
            content: trimmed,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setHasUserMessage(true);

        chatMutation.mutate(
            {
                message: userMessage.content,
                conversation_history: messages.filter(m => m.content && m.content.trim().length > 0).map(m => ({ role: m.role, content: m.content })),
                current_task: currentConfig,
                available_agents: buildAvailableAgentsPayload(),
            },
            {
                onSuccess: apiData => {
                    const data = transformChatResponse(apiData);
                    setMessages(prev => [...prev, { role: "assistant", content: data.message, timestamp: new Date(), inlineComponent: data.inlineComponent }]);
                    if (Object.keys(data.taskUpdates).length > 0) {
                        onConfigUpdate(data.taskUpdates);
                    }
                    onReadyToSave(data.readyToSave);
                },
                onError: error => {
                    addNotification(error instanceof Error ? error.message : "Failed to send message", "warning");
                    setMessages(prev => [...prev, { role: "assistant", content: "I encountered an error. Could you please try again?", timestamp: new Date() }]);
                },
                onSettled: () => {
                    setTimeout(() => inputRef.current?.focus(), 100);
                },
            }
        );
    };

    const handleSend = () => {
        if (!input.trim() || isLoading) return;
        const text = input.trim();
        setInput("");
        sendMessage(text);
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        handleSend();
    };

    const handleAgentPickerSelect = (messageIndex: number, agentName: string) => {
        if (isLoading) return;
        const agent = availableAgents.find(a => a.name === agentName);
        const displayName = agent?.displayName || agentName;
        setMessages(prev => prev.map((m, i) => (i === messageIndex ? { ...m, resolvedAgentName: agentName } : m)));
        onConfigUpdate({ targetAgentName: agentName });
        sendMessage(`Use ${displayName}.`);
    };

    if (isInitializing) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 className="h-8 w-8 animate-spin text-(--primary-wMain)" />
                    <p className="text-sm text-(--secondary-text-wMain)">Initializing AI assistant...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-(--primary-w10)">
                        <Sparkles className="h-4 w-4 text-(--primary-wMain)" />
                    </div>
                    <h3 className="text-sm font-semibold">AI Builder</h3>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
                {messages.map((message, index) => (
                    <div key={index} className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}>
                        <div className={cn(message.inlineComponent ? "w-full py-3" : "max-w-[80%] rounded-2xl px-4 py-3", message.role === "user" && "bg-(--secondary-w20)")}>
                            {message.role === "assistant" ? <MarkdownWrapper content={message.content} className="text-sm leading-relaxed" /> : <div className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</div>}
                            {message.inlineComponent?.type === "agent_picker" && (
                                <AgentPickerCard
                                    prompt={message.inlineComponent.prompt}
                                    suggestions={message.inlineComponent.suggestions}
                                    allowOther={message.inlineComponent.allowOther}
                                    availableAgents={availableAgents}
                                    resolvedAgentName={message.resolvedAgentName}
                                    onSelect={agentName => handleAgentPickerSelect(index, agentName)}
                                />
                            )}
                        </div>
                    </div>
                ))}

                {/* Loading indicator */}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="flex items-center gap-2 rounded-2xl px-4 py-3">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm text-(--secondary-text-wMain)">Thinking...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t bg-(--background-w10) p-4">
                {/* STT Error Banner */}
                {sttError && (
                    <div className="mb-3">
                        <MessageBanner variant="error" message={sttError} dismissible onDismiss={() => setSttError(null)} />
                    </div>
                )}

                <form onSubmit={handleSubmit} className="relative">
                    <Textarea
                        ref={inputRef}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder={isRecording ? "Recording..." : hasUserMessage ? "Type your message..." : "Describe what you want to automate..."}
                        disabled={isLoading || isRecording}
                        className="max-h-[200px] min-h-[40px] resize-none overflow-y-auto pr-24"
                        rows={1}
                        style={{ height: "40px" }}
                    />
                    <div className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-1">
                        {/* Microphone button - show if STT feature enabled and STT setting enabled */}
                        {sttEnabled && settings.speechToText && <AudioRecorder disabled={isLoading} onTranscriptionComplete={handleTranscription} onError={handleTranscriptionError} onRecordingStateChange={setIsRecording} />}
                        <Button type="submit" disabled={!input.trim() || isLoading} variant="ghost" size="icon" tooltip="Send message">
                            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    );
};
