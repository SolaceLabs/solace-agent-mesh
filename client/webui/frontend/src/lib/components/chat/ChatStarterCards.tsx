import React, { useMemo, useState, useRef, useEffect } from "react";

import { BarChart3, Users, ShieldCheck, TrendingUp, FileSearch, Lightbulb, Search, FileText, Database, Globe, Bot, ChevronRight, Briefcase, Code, Mail, Calendar, Settings, Zap, Target, PieChart, LineChart, type LucideIcon } from "lucide-react";

import { useStarterSuggestions } from "@/lib/api/starterSuggestions";
import type { StarterSuggestionCategory } from "@/lib/api/starterSuggestions";

export interface StarterCardOption {
    label: string;
    prompt: string;
}

export interface StarterCard {
    icon: React.ReactNode;
    label: string;
    description: string;
    options: StarterCardOption[];
}

/** Map of icon name strings to Lucide React icon components */
const ICON_MAP: Record<string, LucideIcon> = {
    BarChart3,
    Users,
    ShieldCheck,
    TrendingUp,
    FileSearch,
    Lightbulb,
    Search,
    FileText,
    Database,
    Globe,
    Bot,
    Briefcase,
    Code,
    Mail,
    Calendar,
    Settings,
    Zap,
    Target,
    PieChart,
    LineChart,
};

/** Resolve an icon name string to a React element, with fallback */
function resolveIcon(iconName: string): React.ReactNode {
    const IconComponent = ICON_MAP[iconName] || Lightbulb;
    return <IconComponent className="h-4 w-4" />;
}

/** Convert backend suggestion categories to StarterCard format */
function categoriesToCards(categories: StarterSuggestionCategory[]): StarterCard[] {
    return categories.map(cat => ({
        icon: resolveIcon(cat.icon),
        label: cat.label,
        description: cat.description,
        options: cat.options.map(opt => ({
            label: opt.label,
            prompt: opt.prompt,
        })),
    }));
}

/** Default starter cards shown when LLM suggestions are unavailable */
const DEFAULT_STARTER_CARDS: StarterCard[] = [
    {
        icon: <BarChart3 className="h-4 w-4" />,
        label: "Research & Analysis",
        description: "Investigate topics and analyze data",
        options: [
            { label: "Help me research a topic", prompt: "Help me research a topic in depth. Ask me what I'd like to investigate and I'll provide the details." },
            { label: "Analyze data for insights", prompt: "Help me analyze some data to find patterns and insights. Ask me about the data I'm working with so we can get started." },
            { label: "Compare options or alternatives", prompt: "Help me compare different options or alternatives to make a decision. Ask me what I'm evaluating." },
        ],
    },
    {
        icon: <FileText className="h-4 w-4" />,
        label: "Writing & Editing",
        description: "Draft, rewrite, and improve content",
        options: [
            { label: "Make my message more persuasive", prompt: "Rewrite my message so it feels more persuasive for its audience and goal. If needed, ask me to share the message and what I want it to achieve." },
            { label: "Draft a professional email", prompt: "Help me draft a professional email. Ask me about the recipient, purpose, and key points I want to cover." },
            { label: "Summarize a long document", prompt: "Help me create a concise summary of a document. Ask me to share the content or tell you what it's about." },
        ],
    },
    {
        icon: <Lightbulb className="h-4 w-4" />,
        label: "Planning & Strategy",
        description: "Organize ideas and plan next steps",
        options: [
            { label: "Help me plan a project", prompt: "Help me create a project plan with milestones and tasks. Ask me about the project scope and timeline so we can get started." },
            { label: "Brainstorm solutions", prompt: "Help me brainstorm solutions to a challenge I'm facing. Ask me to describe the problem and any constraints." },
            { label: "Prepare for a meeting", prompt: "Help me prepare for an upcoming meeting. Ask me about the meeting topic, attendees, and what I want to accomplish." },
        ],
    },
    {
        icon: <TrendingUp className="h-4 w-4" />,
        label: "Problem Solving",
        description: "Work through complex challenges",
        options: [
            { label: "Break down a complex problem", prompt: "Help me break down a complex problem into manageable parts. Ask me to describe what I'm dealing with." },
            { label: "Evaluate a decision", prompt: "Help me think through a decision by weighing pros and cons. Ask me about the options I'm considering." },
            { label: "Troubleshoot an issue", prompt: "Help me troubleshoot an issue I'm experiencing. Ask me to describe the problem and what I've already tried." },
        ],
    },
];

const MAX_VISIBLE_CARDS = 4;

/** Loading skeleton for starter cards */
function StarterCardsSkeleton() {
    return (
        <div className="w-full">
            <div className="flex flex-wrap justify-center gap-2 px-4">
                {Array.from({ length: MAX_VISIBLE_CARDS }).map((_, i) => (
                    <div key={i} className="flex items-center gap-2 rounded-full border border-(--secondary-w20) bg-(--background-w10) px-4 py-2.5">
                        <div className="h-4 w-4 animate-pulse rounded bg-(--secondary-w20)" />
                        <div className="h-4 w-20 animate-pulse rounded bg-(--secondary-w20)" />
                    </div>
                ))}
            </div>
        </div>
    );
}

interface ChatStarterCardsProps {
    onOptionClick: (prompt: string) => void;
}

export const ChatStarterCards: React.FC<ChatStarterCardsProps> = ({ onOptionClick }) => {
    const [expandedCard, setExpandedCard] = useState<string | null>(null);
    const expandedRef = useRef<HTMLDivElement>(null);

    // Fetch LLM-generated suggestions
    const { data: suggestionsData, isLoading } = useStarterSuggestions();

    // Close expanded card when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (expandedRef.current && !expandedRef.current.contains(event.target as Node)) {
                setExpandedCard(null);
            }
        };

        if (expandedCard) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [expandedCard]);

    const visibleCards = useMemo(() => {
        // Use LLM-generated suggestions if available, otherwise fall back to defaults
        if (suggestionsData?.categories && suggestionsData.categories.length > 0) {
            const llmCards = categoriesToCards(suggestionsData.categories);
            return llmCards.slice(0, MAX_VISIBLE_CARDS);
        }

        return DEFAULT_STARTER_CARDS.slice(0, MAX_VISIBLE_CARDS);
    }, [suggestionsData]);

    const expandedCardData = useMemo(() => {
        if (!expandedCard) return null;
        return visibleCards.find(card => card.label === expandedCard) ?? null;
    }, [expandedCard, visibleCards]);

    const handleCardClick = (cardLabel: string) => {
        setExpandedCard(prev => (prev === cardLabel ? null : cardLabel));
    };

    const handleOptionClick = (prompt: string) => {
        setExpandedCard(null);
        onOptionClick(prompt);
    };

    if (isLoading) {
        return <StarterCardsSkeleton />;
    }

    return (
        <div className="w-full" ref={expandedRef}>
            {/* Show pills when no card is expanded */}
            {!expandedCardData && (
                <div className="flex flex-wrap justify-center gap-2 px-4">
                    {visibleCards.map(card => (
                        <button
                            key={card.label}
                            onClick={() => handleCardClick(card.label)}
                            className="group flex items-center gap-2 rounded-full border border-(--secondary-w20) bg-(--background-w10) px-4 py-2.5 text-sm transition-all duration-200 hover:border-(--secondary-w40) hover:bg-(--background-w20) hover:shadow-sm active:scale-[0.98]"
                            title={card.description}
                        >
                            <span className="text-(--secondary-text-wMain) transition-colors group-hover:text-(--primary-wMain)">{card.icon}</span>
                            <span className="font-medium text-(--foreground)">{card.label}</span>
                        </button>
                    ))}
                </div>
            )}

            {/* Show expanded options (replacing pills) when a card is expanded */}
            {expandedCardData && (
                <div className="animate-in fade-in slide-in-from-top-2 w-full duration-200">
                    <div className="flex flex-col">
                        {expandedCardData.options.map((option, index) => (
                            <button
                                key={option.label}
                                onClick={() => handleOptionClick(option.prompt)}
                                className={`group flex w-full items-center gap-3 px-6 py-3.5 text-left text-sm transition-colors hover:bg-(--background-w20) ${index < expandedCardData.options.length - 1 ? "border-b border-(--secondary-w20)" : ""}`}
                            >
                                <span className="text-(--secondary-text-wMain) transition-colors group-hover:text-(--primary-wMain)">{expandedCardData.icon}</span>
                                <span className="flex-1 text-(--primary-text-wMain)">{option.label}</span>
                                <ChevronRight className="h-4 w-4 text-(--secondary-text-wMain) opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
