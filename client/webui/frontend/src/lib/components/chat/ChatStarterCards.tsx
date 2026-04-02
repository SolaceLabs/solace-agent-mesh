import { useMemo, useState, useRef, useEffect } from "react";

import { BarChart3, Users, ShieldCheck, TrendingUp, FileSearch, Lightbulb, Search, FileText, Database, Globe, Bot, ChevronRight, Briefcase, Code, Mail, Calendar, Settings, Zap, Target, PieChart, LineChart, type LucideIcon } from "lucide-react";

import { Button } from "@/lib/components/ui";
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

export function ChatStarterCards({ onOptionClick }: ChatStarterCardsProps) {
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
        if (suggestionsData?.categories && suggestionsData.categories.length > 0) {
            return categoriesToCards(suggestionsData.categories).slice(0, MAX_VISIBLE_CARDS);
        }

        return [];
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

    if (visibleCards.length === 0) {
        return null;
    }

    return (
        <div className="w-full" ref={expandedRef}>
            {/* Show pills when no card is expanded */}
            {!expandedCardData && (
                <div className="flex flex-wrap justify-center gap-2 px-4">
                    {visibleCards.map(card => (
                        <Button
                            key={card.label}
                            variant="outline"
                            onClick={() => handleCardClick(card.label)}
                            className="group flex items-center gap-2 rounded-full border border-(--secondary-w20) bg-(--background-w10) px-4 py-2.5 text-sm transition-all duration-200 hover:border-(--secondary-w40) hover:bg-(--background-w20) hover:shadow-sm active:scale-[0.98]"
                            title={card.description}
                        >
                            <span className="text-(--secondary-text-wMain) transition-colors group-hover:text-(--primary-wMain)">{card.icon}</span>
                            <span className="font-medium text-(--foreground)">{card.label}</span>
                        </Button>
                    ))}
                </div>
            )}

            {/* Show expanded options (replacing pills) when a card is expanded */}
            {expandedCardData && (
                <div className="animate-in fade-in slide-in-from-top-2 w-full duration-200">
                    <div className="flex flex-col">
                        {expandedCardData.options.map((option, index) => (
                            <Button
                                key={option.label}
                                variant="ghost"
                                onClick={() => handleOptionClick(option.prompt)}
                                className={`group flex w-full items-center gap-3 px-6 py-3.5 text-left text-sm transition-colors hover:bg-(--background-w20) ${index < expandedCardData.options.length - 1 ? "border-b border-(--secondary-w20)" : ""}`}
                            >
                                <span className="text-(--secondary-text-wMain) transition-colors group-hover:text-(--primary-wMain)">{expandedCardData.icon}</span>
                                <span className="flex-1 text-(--primary-text-wMain)">{option.label}</span>
                                <ChevronRight className="h-4 w-4 text-(--secondary-text-wMain) opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
                            </Button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
