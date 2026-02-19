import type { Citation as CitationType } from "@/lib/utils/citations";

export const documentCitation: CitationType = {
    marker: "[[cite:idx0r0]]",
    type: "document",
    sourceId: 0,
    position: 0,
    citationId: "idx0r0",
    source: {
        citationId: "idx0r0",
        filename: "quarterly_report.pdf",
        contentPreview: "Revenue increased by 15% in Q4...",
        relevanceScore: 0.95,
        metadata: {
            location_range: "Pages 3-5",
            primary_location: "Page 3",
        },
    },
};

export const webSearchCitation: CitationType = {
    marker: "[[cite:s0r0]]",
    type: "search",
    sourceId: 0,
    position: 0,
    citationId: "s0r0",
    source: {
        citationId: "s0r0",
        sourceUrl: "https://example.com/article/latest-news",
        contentPreview: "The latest developments in AI technology...",
        relevanceScore: 0.88,
        metadata: {
            type: "web_search",
            title: "Latest Technology News - Example.com",
            link: "https://example.com/article/latest-news",
        },
    },
};

export const researchCitation: CitationType = {
    marker: "[[cite:research0]]",
    type: "research",
    sourceId: 0,
    position: 0,
    citationId: "research0",
    source: {
        citationId: "research0",
        sourceUrl: "https://research.university.edu/papers/ai-advances-2024",
        title: "Advances in Artificial Intelligence 2024",
        contentPreview: "This paper presents a comprehensive review of AI advances...",
        relevanceScore: 0.92,
        metadata: {
            type: "deep_research",
            title: "Advances in Artificial Intelligence 2024",
        },
    },
};

export const multipleDocumentCitations: CitationType[] = [
    documentCitation,
    {
        marker: "[[cite:idx0r1]]",
        type: "document",
        sourceId: 1,
        position: 0,
        citationId: "idx0r1",
        source: {
            citationId: "idx0r1",
            filename: "annual_summary.pdf",
            contentPreview: "Key highlights from the year...",
            relevanceScore: 0.91,
            metadata: {
                location_range: "Pages 10-12",
            },
        },
    },
    {
        marker: "[[cite:idx0r2]]",
        type: "document",
        sourceId: 2,
        position: 0,
        citationId: "idx0r2",
        source: {
            citationId: "idx0r2",
            filename: "market_analysis.pdf",
            contentPreview: "Market trends indicate...",
            relevanceScore: 0.87,
            metadata: {
                location_range: "Page 7",
            },
        },
    },
];

export const multipleWebCitations: CitationType[] = [
    webSearchCitation,
    {
        marker: "[[cite:s0r1]]",
        type: "search",
        sourceId: 1,
        position: 0,
        citationId: "s0r1",
        source: {
            citationId: "s0r1",
            sourceUrl: "https://techblog.io/ai-revolution",
            contentPreview: "The AI revolution is transforming industries...",
            relevanceScore: 0.85,
            metadata: {
                type: "web_search",
                title: "The AI Revolution - TechBlog",
            },
        },
    },
    {
        marker: "[[cite:s0r2]]",
        type: "search",
        sourceId: 2,
        position: 0,
        citationId: "s0r2",
        source: {
            citationId: "s0r2",
            sourceUrl: "https://news.site/tech/machine-learning",
            contentPreview: "Machine learning algorithms...",
            relevanceScore: 0.82,
            metadata: {
                type: "web_search",
                title: "Machine Learning Trends - News Site",
            },
        },
    },
];

export const multipleResearchCitations: CitationType[] = [
    researchCitation,
    {
        marker: "[[cite:research1]]",
        type: "research",
        sourceId: 1,
        position: 0,
        citationId: "research1",
        source: {
            citationId: "research1",
            sourceUrl: "https://arxiv.org/abs/2024.12345",
            title: "Deep Learning in Healthcare",
            contentPreview: "Applications of deep learning in medical diagnosis...",
            relevanceScore: 0.89,
            metadata: {
                type: "deep_research",
                title: "Deep Learning in Healthcare",
            },
        },
    },
];
