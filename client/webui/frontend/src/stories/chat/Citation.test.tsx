/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { BundledCitations } from "@/lib/components/chat/Citation";
import { documentCitation, multipleDocumentCitations } from "../mocks/citations";

expect.extend(matchers);

describe("BundledCitations edge cases", () => {
    test("renders nothing when citations array is empty", async () => {
        const { container } = render(<BundledCitations citations={[]} />);
        const buttons = container.querySelectorAll("button");
        expect(buttons).toHaveLength(0);
    });

    test("deduplicates citations by sourceId and type", async () => {
        const citationsWithDuplicates = [documentCitation, documentCitation, multipleDocumentCitations[1]];

        render(<BundledCitations citations={citationsWithDuplicates} />);

        const badge = await screen.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("+1");
    });
});
