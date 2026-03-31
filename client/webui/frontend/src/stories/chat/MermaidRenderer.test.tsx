/// <reference types="@testing-library/jest-dom" />
import { render, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

// Mock @use-gesture/react for jsdom
vi.mock("@use-gesture/react", () => ({
    useGesture: () => () => ({}),
}));

import { MermaidRenderer } from "@/lib/components/chat/preview/Renderers/MermaidRenderer";

describe("MermaidRenderer", () => {
    let setRenderError: (error: string | null) => void;

    beforeEach(() => {
        setRenderError = vi.fn<(error: string | null) => void>();
        // Avoid verbose errors in jsdom (getBBox not available, etc.)
        vi.spyOn(console, "error").mockImplementation(() => {});
    });

    test("sets render error for invalid diagram syntax", async () => {
        render(<MermaidRenderer content="not a valid diagram at all" setRenderError={setRenderError} />);

        await waitFor(() => {
            expect(setRenderError).toHaveBeenCalledWith(expect.stringContaining("No diagram type detected"));
        });
    });

    describe("input validation (XSS prevention)", () => {
        const dangerousInputs = [
            { name: "script tags", content: 'graph TD; A["<script>alert(1)</script>"]-->B;' },
            { name: "javascript: protocol", content: 'graph TD; click A "javascript:alert(1)"' },
            { name: "event handlers", content: 'graph TD; A["<div onclick=alert(1)>"]-->B;' },
            { name: "iframe injection", content: 'graph TD; A["<iframe src=evil.com>"]-->B;' },
            { name: "object embed", content: 'graph TD; A["<object data=evil.swf>"]-->B;' },
            { name: "embed tag", content: 'graph TD; A["<embed src=evil>"]-->B;' },
            { name: "data URI with HTML", content: 'graph TD; click A "data:text/html,<script>alert(1)</script>"' },
        ];

        for (const { name, content } of dangerousInputs) {
            test(`rejects ${name}`, async () => {
                render(<MermaidRenderer content={content} setRenderError={setRenderError} />);

                await waitFor(() => {
                    expect(setRenderError).toHaveBeenCalledWith("Invalid diagram content: potentially unsafe patterns detected");
                });
            });
        }
    });

    test("clears error on successful re-render after failure", async () => {
        const { rerender } = render(<MermaidRenderer content="not valid" setRenderError={setRenderError} />);

        await waitFor(() => {
            expect(setRenderError).toHaveBeenCalledWith(expect.stringContaining("No diagram type detected"));
        });

        (setRenderError as ReturnType<typeof vi.fn>).mockClear();

        rerender(<MermaidRenderer content="graph TD; A-->B;" setRenderError={setRenderError} />);

        await waitFor(() => {
            expect(setRenderError).toHaveBeenCalledWith(null);
        });
    });
});
