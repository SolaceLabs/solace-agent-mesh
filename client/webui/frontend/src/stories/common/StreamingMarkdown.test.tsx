/// <reference types="@testing-library/jest-dom" />
import { render, waitFor } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { StreamingMarkdown } from "@/lib/components/common/StreamingMarkdown";
import type { Citation } from "@/lib/utils/citations";

expect.extend(matchers);

const documentCitation: Citation = {
    marker: "[[cite:idx0r0]]",
    type: "document",
    sourceId: 0,
    position: 0,
    citationId: "idx0r0",
    source: {
        citationId: "idx0r0",
        filename: "report.pdf",
        contentPreview: "...",
        relevanceScore: 0.9,
        metadata: {
            primary_location: "Page 7",
        },
    },
};

// The streaming animation advances content over real time via requestAnimationFrame.
// Tests use waitFor with a generous timeout so the animation can flush short content.
const WAIT = { timeout: 4000 };

describe("StreamingMarkdown", () => {
    test("eventually renders markdown via MarkdownHTMLConverter when no citations are provided", async () => {
        const { container } = render(<StreamingMarkdown content={"# hello\n\nworld"} />);

        // Wait for the trailing paragraph so we know the animation has flushed the full content.
        await waitFor(() => {
            expect(container.querySelector("p")?.textContent).toBe("world");
        }, WAIT);

        const heading = container.querySelector("h1");
        expect(heading).not.toBeNull();
        expect(heading!.textContent).toBe("hello");
    });

    test("forwards className to MarkdownHTMLConverter when no citations are provided", async () => {
        const { container } = render(<StreamingMarkdown content="plain text" className="custom-stream" />);

        await waitFor(() => {
            const wrapper = container.querySelector(".custom-stream");
            expect(wrapper).not.toBeNull();
            expect(wrapper!.textContent).toContain("plain text");
        }, WAIT);
    });

    test("renders citation bubbles inline when citations are present", async () => {
        const content = "Per the report [[cite:idx0r0]], revenue grew.";

        const { container } = render(<StreamingMarkdown content={content} citations={[documentCitation]} />);

        // Wait for the trailing text so the animation has flushed the full content,
        // including the citation marker that precedes it.
        await waitFor(() => {
            expect(container.textContent).toContain("revenue grew.");
        }, WAIT);

        const badge = container.querySelector("button.citation-badge");
        expect(badge).not.toBeNull();
        expect(badge!.textContent).toContain("report.pdf");
        expect(badge!.textContent).toContain("Page 7");

        // Surrounding markdown text is preserved and the raw cite marker is consumed.
        expect(container.textContent).toContain("Per the report");
        expect(container.textContent).not.toContain("[[cite:idx0r0]]");
    });

    test("renders via MarkdownHTMLConverter when citations array is empty", async () => {
        const { container } = render(<StreamingMarkdown content="just text" citations={[]} />);

        await waitFor(() => {
            expect(container.querySelector("p")?.textContent).toBe("just text");
        }, WAIT);
        expect(container.querySelector("button.citation-badge")).toBeNull();
    });
});
