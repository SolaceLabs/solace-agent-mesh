import type { Citation as CitationType } from "@/lib/utils/citations";
import type { RAGSearchResult } from "@/lib/types";

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

// Mock RAGSearchResult data for document_search type
export const documentSearchRagData: RAGSearchResult[] = [
    {
        query: "quarterly revenue performance",
        searchType: "document_search",
        turnNumber: 1,
        timestamp: new Date().toISOString(),
        taskId: "task-123",
        sources: [
            {
                citationId: "idx0r0",
                filename: "quarterly_report_q4_2024.pdf",
                contentPreview: "Revenue increased by 15% in Q4 compared to the previous quarter. The growth was primarily driven by strong performance in the enterprise segment...",
                relevanceScore: 0.95,
                metadata: {
                    location_range: "Pages 3-5",
                    primary_location: "Page 3",
                },
            },
            {
                citationId: "idx0r1",
                filename: "quarterly_report_q4_2024.pdf",
                contentPreview: "Operating expenses decreased by 8% due to cost optimization initiatives implemented in Q3...",
                relevanceScore: 0.91,
                metadata: {
                    location_range: "Page 5",
                    primary_location: "Page 5",
                },
            },
            {
                citationId: "idx0r2",
                filename: "quarterly_report_q4_2024.pdf",
                contentPreview: "Net profit margin improved to 18.5%, up from 15.2% in the same quarter last year...",
                relevanceScore: 0.89,
                metadata: {
                    location_range: "Page 3",
                    primary_location: "Page 3",
                },
            },
            {
                citationId: "idx0r3",
                filename: "annual_summary_2024.pdf",
                contentPreview: "Key highlights from the fiscal year include record revenue of $4.2B and successful expansion into three new markets...",
                relevanceScore: 0.87,
                metadata: {
                    location_range: "Pages 10-12",
                    primary_location: "Page 10",
                },
            },
            {
                citationId: "idx0r4",
                filename: "annual_summary_2024.pdf",
                contentPreview: "Customer acquisition cost decreased by 22% while customer lifetime value increased by 35%...",
                relevanceScore: 0.85,
                metadata: {
                    location_range: "Page 15",
                    primary_location: "Page 15",
                },
            },
            {
                citationId: "idx0r5",
                filename: "market_analysis_report.txt",
                contentPreview: "Market trends indicate strong demand for AI-powered solutions in the healthcare sector...",
                relevanceScore: 0.82,
                metadata: {
                    location_range: "Page 7",
                    primary_location: "Page 7",
                },
            },
        ],
    },
];

// Single document with one page
export const singleDocumentSinglePage: RAGSearchResult[] = [
    {
        query: "product specifications",
        searchType: "document_search",
        turnNumber: 1,
        timestamp: new Date().toISOString(),
        taskId: "task-456",
        sources: [
            {
                citationId: "idx1r0",
                filename: "product_specs.pdf",
                contentPreview: "The product specifications include detailed measurements and material requirements...",
                relevanceScore: 0.93,
                metadata: {
                    location_range: "Page 1",
                    primary_location: "Page 1",
                },
            },
        ],
    },
];

// Document with no page metadata (edge case)
export const documentWithNoPageMetadata: RAGSearchResult[] = [
    {
        query: "unknown document location",
        searchType: "document_search",
        turnNumber: 1,
        timestamp: new Date().toISOString(),
        taskId: "task-789",
        sources: [
            {
                citationId: "idx2r0",
                filename: "legacy_document.pdf",
                contentPreview: "This document contains important historical data...",
                relevanceScore: 0.88,
                metadata: {},
            },
            {
                citationId: "idx2r1",
                filename: "legacy_document.pdf",
                contentPreview: "Additional context from the same document...",
                relevanceScore: 0.84,
                metadata: {},
            },
        ],
    },
];

// Multiple documents with overlapping pages
export const multipleDocumentsOverlappingPages: RAGSearchResult[] = [
    {
        query: "financial projections",
        searchType: "document_search",
        turnNumber: 1,
        timestamp: new Date().toISOString(),
        taskId: "task-101",
        sources: [
            {
                citationId: "idx3r0",
                filename: "budget_2025.pdf",
                contentPreview: "Budget projections for Q1 2025...",
                relevanceScore: 0.94,
                metadata: {
                    location_range: "Page 3",
                    primary_location: "Page 3",
                },
            },
            {
                citationId: "idx3r1",
                filename: "forecast_report.pdf",
                contentPreview: "Revenue forecast indicates 20% growth...",
                relevanceScore: 0.92,
                metadata: {
                    location_range: "Page 3",
                    primary_location: "Page 3",
                },
            },
            {
                citationId: "idx3r2",
                filename: "budget_2025.pdf",
                contentPreview: "Operating expense projections...",
                relevanceScore: 0.9,
                metadata: {
                    location_range: "Page 3",
                    primary_location: "Page 3",
                },
            },
            {
                citationId: "idx3r3",
                filename: "forecast_report.pdf",
                contentPreview: "Market expansion strategy details...",
                relevanceScore: 0.88,
                metadata: {
                    location_range: "Page 5",
                    primary_location: "Page 5",
                },
            },
        ],
    },
];
