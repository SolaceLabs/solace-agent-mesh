import React, { useState, useEffect, useRef } from 'react';
import { Bot, Send, Loader2, Sparkles, User } from 'lucide-react';
import { Button, Input, Badge } from '@/lib/components/ui';
import type { TemplateConfig } from './hooks/usePromptTemplateBuilder';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface ChatResponse {
    message: string;
    template_updates: Record<string, any>;
    confidence: number;
    ready_to_save: boolean;
}

interface PromptBuilderChatProps {
    onConfigUpdate: (config: Partial<TemplateConfig>) => void;
    currentConfig: TemplateConfig;
    onReadyToSave: (ready: boolean) => void;
}

export const PromptBuilderChat: React.FC<PromptBuilderChatProps> = ({
    onConfigUpdate,
    currentConfig,
    onReadyToSave,
}) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isInitializing, setIsInitializing] = useState(true);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Auto-scroll to bottom when new messages arrive
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Initialize chat with greeting
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
    }, []);

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

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleSuggestionClick = (suggestion: string) => {
        setInput(suggestion);
        inputRef.current?.focus();
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
            <div className="border-b bg-gradient-to-r from-primary/5 to-primary/10 px-4 py-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                        <Sparkles className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">AI Template Builder</h3>
                        <p className="text-xs text-muted-foreground">
                            Describe your task and I'll create a template
                        </p>
                    </div>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message, index) => (
                    <div
                        key={index}
                        className={`flex gap-3 ${
                            message.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                    >
                        {message.role === 'assistant' && (
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                                <Bot className="h-4 w-4 text-primary" />
                            </div>
                        )}

                        <div
                            className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                                message.role === 'user'
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-muted'
                            }`}
                        >
                            <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                {message.content}
                            </div>
                            <div className="mt-1 text-xs opacity-70">
                                {message.timestamp.toLocaleTimeString([], {
                                    hour: '2-digit',
                                    minute: '2-digit',
                                })}
                            </div>
                        </div>

                        {message.role === 'user' && (
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                                <User className="h-4 w-4 text-primary" />
                            </div>
                        )}
                    </div>
                ))}

                {/* Loading indicator */}
                {isLoading && (
                    <div className="flex gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                            <Bot className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex items-center gap-2 rounded-2xl bg-muted px-4 py-3">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-sm text-muted-foreground">Thinking...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t bg-background p-4">
                <div className="flex gap-2">
                    <Input
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Describe your recurring task..."
                        disabled={isLoading}
                        className="flex-1"
                    />
                    <Button
                        onClick={handleSend}
                        disabled={!input.trim() || isLoading}
                        size="icon"
                        className="shrink-0"
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Send className="h-4 w-4" />
                        )}
                    </Button>
                </div>

                {/* Quick suggestions */}
                <div className="mt-3 flex flex-wrap gap-2">
                    <span className="text-xs text-muted-foreground">Quick start:</span>
                    {[
                        'Code review template',
                        'Bug report template',
                        'Meeting notes template',
                    ].map((suggestion) => (
                        <Badge
                            key={suggestion}
                            variant="outline"
                            className="cursor-pointer hover:bg-primary/10 transition-colors"
                            onClick={() => handleSuggestionClick(suggestion)}
                        >
                            {suggestion}
                        </Badge>
                    ))}
                </div>
            </div>
        </div>
    );
};