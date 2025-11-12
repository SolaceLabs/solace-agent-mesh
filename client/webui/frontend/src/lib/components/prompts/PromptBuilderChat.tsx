import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Sparkles } from 'lucide-react';
import { Button, Textarea } from '@/lib/components/ui';
import type { TemplateConfig } from './hooks/usePromptTemplateBuilder';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface ChatResponse {
    message: string;
    template_updates: Record<string, unknown>;
    confidence: number;
    ready_to_save: boolean;
}

interface PromptBuilderChatProps {
    onConfigUpdate: (config: Partial<TemplateConfig>) => void;
    currentConfig: TemplateConfig;
    onReadyToSave: (ready: boolean) => void;
    initialMessage?: string | null;
}

export const PromptBuilderChat: React.FC<PromptBuilderChatProps> = ({
    onConfigUpdate,
    currentConfig,
    onReadyToSave,
    initialMessage,
}) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isInitializing, setIsInitializing] = useState(true);
    const [hasUserMessage, setHasUserMessage] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // Auto-scroll to bottom when new messages arrive
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Initialize chat with greeting and optionally send initial message
    useEffect(() => {
        const initChat = async () => {
            try {
                const response = await fetch('/api/v1/prompts/chat/init');
                const data = await response.json();

                setMessages([
                    {
                        role: 'assistant',
                        content: data.message,
                        timestamp: new Date(),
                    },
                ]);

                // If there's an initial message, send it automatically
                if (initialMessage) {
                    setHasUserMessage(true);
                    const userMessage: Message = {
                        role: 'user',
                        content: initialMessage,
                        timestamp: new Date(),
                    };
                    setMessages(prev => [...prev, userMessage]);
                    
                    // Scroll to bottom after adding user message
                    setTimeout(() => scrollToBottom(), 100);
                    
                    setIsLoading(true);

                    // Send the message to the API
                    try {
                        const chatResponse = await fetch('/api/v1/prompts/chat', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            credentials: 'include',
                            body: JSON.stringify({
                                message: initialMessage,
                                conversation_history: [
                                    {
                                        role: 'assistant',
                                        content: data.message,
                                    },
                                ],
                                current_template: currentConfig,
                            }),
                        });

                        if (chatResponse.ok) {
                            const chatData: ChatResponse = await chatResponse.json();
                            
                            const assistantMessage: Message = {
                                role: 'assistant',
                                content: chatData.message,
                                timestamp: new Date(),
                            };
                            setMessages(prev => [...prev, assistantMessage]);

                            if (Object.keys(chatData.template_updates).length > 0) {
                                onConfigUpdate(chatData.template_updates);
                            }

                            onReadyToSave(chatData.ready_to_save);
                            
                            // Scroll to bottom after AI response
                            setTimeout(() => scrollToBottom(), 100);
                        } else {
                            const errorData = await chatResponse.json().catch(() => ({}));
                            console.error('Prompt builder API error:', errorData);
                            
                            const errorMessage: Message = {
                                role: 'assistant',
                                content: 'The conversation history is too long for automatic processing. Please describe your task manually, and I\'ll help you create a template.',
                                timestamp: new Date(),
                            };
                            setMessages(prev => [...prev, errorMessage]);
                        }
                    } catch (error) {
                        console.error('Error sending initial message:', error);
                        const errorMessage: Message = {
                            role: 'assistant',
                            content: 'I encountered an error processing your request. Please try describing your task manually.',
                            timestamp: new Date(),
                        };
                        setMessages(prev => [...prev, errorMessage]);
                    } finally {
                        setIsLoading(false);
                    }
                }
            } catch (error) {
                console.error('Failed to initialize chat:', error);
                setMessages([
                    {
                        role: 'assistant',
                        content: "Hi! I'll help you create a prompt template. What kind of recurring task would you like to template?",
                        timestamp: new Date(),
                    },
                ]);
            } finally {
                setIsInitializing(false);
            }
        };

        initChat();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Only run once on mount

    // Auto-focus input when component mounts and is not loading
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
            textarea.style.height = 'auto';
            // Set height based on scrollHeight, with max height of 200px
            const newHeight = Math.min(textarea.scrollHeight, 200);
            textarea.style.height = `${newHeight}px`;
        };

        adjustHeight();
    }, [input]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            role: 'user',
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);
        setHasUserMessage(true);

        try {
            const response = await fetch('/api/v1/prompts/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    message: userMessage.content,
                    conversation_history: messages
                        .filter((m) => m.content && m.content.trim().length > 0)
                        .map((m) => ({
                            role: m.role,
                            content: m.content,
                        })),
                    current_template: currentConfig,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to get response');
            }

            const data: ChatResponse = await response.json();

            // Add assistant response
            const assistantMessage: Message = {
                role: 'assistant',
                content: data.message,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);

            // Update config if there are updates
            if (Object.keys(data.template_updates).length > 0) {
                onConfigUpdate(data.template_updates);
            }

            // Notify parent if ready to save
            onReadyToSave(data.ready_to_save);
        } catch (error) {
            console.error('Error sending message:', error);
            const errorMessage: Message = {
                role: 'assistant',
                content: 'I encountered an error. Could you please try again?',
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
            // Focus input after response
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        handleSend();
    };

    if (isInitializing) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">Initializing AI assistant...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                        <Sparkles className="h-4 w-4 text-primary" />
                    </div>
                    <h3 className="font-semibold text-sm">AI Template Builder</h3>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message, index) => (
                    <div
                        key={index}
                        className={`flex ${
                            message.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                    >
                        <div
                            className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                                message.role === 'user'
                                    ? 'bg-[var(--message-background)]'
                                    : ''
                            }`}
                        >
                            <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                {message.content}
                            </div>
                        </div>
                    </div>
                ))}

                {/* Loading indicator */}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="flex items-center gap-2 rounded-2xl px-4 py-3">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm text-muted-foreground">Thinking...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t bg-background p-4">
                <form onSubmit={handleSubmit} className="relative">
                    <Textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder={hasUserMessage ? "Type your message..." : "Describe your recurring task..."}
                        disabled={isLoading}
                        className="max-h-[200px] min-h-[40px] resize-none pr-12 overflow-y-auto"
                        rows={1}
                        style={{ height: '40px' }}
                    />
                    <Button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-1/2 -translate-y-1/2"
                        tooltip="Send message"
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Send className="h-4 w-4" />
                        )}
                    </Button>
                </form>
            </div>
        </div>
    );
};