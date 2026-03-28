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

/** Default enterprise-focused starter cards shown when LLM suggestions are unavailable */
const DEFAULT_STARTER_CARDS: StarterCard[] = [
    {
        icon: <BarChart3 className="h-4 w-4" />,
        label: "Competitive Research",
        description: "Analyze market position and competitors",
        options: [
            {
                label: "Compare against top 3 competitors",
                prompt: "Conduct a competitive analysis comparing our company's market position against our top 3 competitors. Include market share, product differentiation, pricing strategies, and recent strategic moves.",
            },
            { label: "Identify market trends", prompt: "Research and summarize the latest market trends in our industry. Identify emerging opportunities, potential disruptions, and how competitors are positioning themselves." },
            { label: "SWOT analysis of our position", prompt: "Perform a SWOT analysis of our company's current market position. Identify our key strengths, weaknesses, opportunities, and threats relative to our competitive landscape." },
            { label: "Pricing strategy comparison", prompt: "Analyze the pricing strategies of our main competitors. Compare pricing models, tiers, and value propositions to identify opportunities for our pricing optimization." },
        ],
    },
    {
        icon: <Users className="h-4 w-4" />,
        label: "Customer Insights",
        description: "Discover trends from customer data",
        options: [
            { label: "Analyze customer pain points", prompt: "Analyze our customer feedback data to identify the top pain points and friction areas. Provide actionable recommendations for improving customer experience." },
            { label: "Customer satisfaction drivers", prompt: "Identify the key drivers of customer satisfaction from our feedback data. What are customers most happy about and what keeps them loyal?" },
            { label: "Churn risk analysis", prompt: "Analyze customer behavior patterns to identify early warning signs of churn. What factors most strongly predict customer attrition?" },
            { label: "Segment customer feedback", prompt: "Segment our customer feedback by customer type, product area, and sentiment. Identify patterns unique to each segment." },
        ],
    },
    {
        icon: <ShieldCheck className="h-4 w-4" />,
        label: "Compliance Report",
        description: "Review regulatory status and risks",
        options: [
            { label: "Regulatory status overview", prompt: "Generate a compliance status report covering our current regulatory obligations, recent policy changes, and any areas requiring immediate attention." },
            { label: "Risk assessment summary", prompt: "Perform a risk assessment of our current compliance posture. Identify high-risk areas, gaps in controls, and recommended remediation steps." },
            { label: "Policy change impact analysis", prompt: "Analyze recent regulatory and policy changes that affect our industry. Summarize the impact on our operations and required actions." },
            { label: "Audit preparation checklist", prompt: "Create a comprehensive audit preparation checklist based on our regulatory requirements. Include documentation needs, control evidence, and timeline recommendations." },
        ],
    },
    {
        icon: <TrendingUp className="h-4 w-4" />,
        label: "Business Strategy",
        description: "Plan initiatives and growth strategy",
        options: [
            { label: "Quarterly strategic plan", prompt: "Help me develop a strategic plan for the next quarter. Analyze current performance metrics, identify growth opportunities, and recommend key initiatives with expected ROI." },
            { label: "Growth opportunity analysis", prompt: "Identify and evaluate the top growth opportunities for our business. Consider market expansion, product development, partnerships, and operational improvements." },
            { label: "KPI dashboard review", prompt: "Review our key performance indicators and provide insights on trends, areas of concern, and recommendations for improvement across all business units." },
            { label: "Resource allocation plan", prompt: "Help me optimize resource allocation across our key initiatives. Analyze current spending, expected returns, and recommend rebalancing for maximum impact." },
        ],
    },
    {
        icon: <FileSearch className="h-4 w-4" />,
        label: "Data Analysis",
        description: "Extract insights from your data",
        options: [
            { label: "Find patterns and trends", prompt: "Help me analyze a dataset to uncover key patterns, trends, and anomalies. I need statistical summaries and actionable insights from the data." },
            { label: "Create data visualizations", prompt: "Recommend the best data visualizations for my dataset. Suggest chart types, key metrics to highlight, and how to tell a compelling data story." },
            { label: "Statistical summary report", prompt: "Generate a comprehensive statistical summary of my data including distributions, correlations, outliers, and key metrics with interpretations." },
            { label: "Anomaly detection", prompt: "Analyze my data for anomalies and unusual patterns. Identify outliers, unexpected trends, and potential data quality issues that need investigation." },
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
