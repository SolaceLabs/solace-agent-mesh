/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { Sources } from "@/lib/components/web/Sources";
import type { RAGSource } from "@/lib/types/fe";

expect.extend(matchers);

const mockSources: RAGSource[] = [
    {
        citationId: "c1",
        sourceUrl: "https://example.com/page1",
        sourceType: "web",
        metadata: { title: "Example Page 1", link: "https://example.com/page1" },
        contentPreview: "Some preview text",
        relevanceScore: 0.9,
    },
    {
        citationId: "c2",
        sourceUrl: "https://example.com/page2",
        sourceType: "web",
        metadata: { title: "Example Page 2", link: "https://example.com/page2" },
        contentPreview: "More preview text",
        relevanceScore: 0.8,
    },
];

describe("Sources", () => {
    test("renders source count when sources are provided", () => {
        render(<Sources ragMetadata={{ sources: mockSources }} />);
        expect(screen.getByText("2 sources")).toBeInTheDocument();
    });

    test("renders nothing when no sources provided", () => {
        const { container } = render(<Sources ragMetadata={{ sources: [] }} />);
        expect(container.firstChild).toBeNull();
    });

    test("clicking the container calls onDeepResearchClick", () => {
        const onClick = vi.fn();
        render(<Sources ragMetadata={{ sources: mockSources }} onDeepResearchClick={onClick} />);
        fireEvent.click(screen.getByRole("button"));
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    test("pressing Enter calls onDeepResearchClick", () => {
        const onClick = vi.fn();
        render(<Sources ragMetadata={{ sources: mockSources }} onDeepResearchClick={onClick} />);
        fireEvent.keyDown(screen.getByRole("button"), { key: "Enter" });
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    test("pressing Space calls onDeepResearchClick", () => {
        const onClick = vi.fn();
        render(<Sources ragMetadata={{ sources: mockSources }} onDeepResearchClick={onClick} />);
        fireEvent.keyDown(screen.getByRole("button"), { key: " " });
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    test("without onDeepResearchClick there is no role=button", () => {
        render(<Sources ragMetadata={{ sources: mockSources }} />);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});

describe("Sources source type branches", () => {
    test("document source type renders as a source", () => {
        const docSource: RAGSource = {
            citationId: "d1",
            sourceType: "document",
            filename: "report.pdf",
            contentPreview: "doc content",
            relevanceScore: 0.9,
            metadata: {},
        };
        render(<Sources ragMetadata={{ sources: [docSource] }} />);
        expect(screen.getByText("1 source")).toBeInTheDocument();
    });

    test("image source type renders as a source", () => {
        const imgSource: RAGSource = {
            citationId: "i1",
            sourceType: "image",
            sourceUrl: "https://example.com/img-page",
            contentPreview: "image content",
            relevanceScore: 0.8,
            metadata: { title: "An image page" },
        };
        render(<Sources ragMetadata={{ sources: [imgSource] }} />);
        expect(screen.getByText("1 source")).toBeInTheDocument();
    });

    test("duplicate web sources are deduplicated", () => {
        const dup1: RAGSource = {
            citationId: "w1",
            sourceType: "web",
            sourceUrl: "https://example.com/same",
            contentPreview: "text",
            relevanceScore: 0.9,
            metadata: { title: "Same Page" },
        };
        const dup2: RAGSource = { ...dup1, citationId: "w2" };
        render(<Sources ragMetadata={{ sources: [dup1, dup2] }} />);
        expect(screen.getByText("1 source")).toBeInTheDocument();
    });
});