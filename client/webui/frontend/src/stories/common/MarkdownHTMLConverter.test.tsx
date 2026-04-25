/// <reference types="@testing-library/jest-dom" />
import { render } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { MarkdownHTMLConverter } from "@/lib/components/common/MarkdownHTMLConverter";

expect.extend(matchers);

const renderMd = (md: string) => render(<MarkdownHTMLConverter>{md}</MarkdownHTMLConverter>);

describe("MarkdownHTMLConverter — GFM task lists", () => {
    test("replaces unchecked checkbox <input> with a styled span (transparent, currentColor border, dimmed)", () => {
        const { container } = renderMd("- [ ] Open task");

        // Native input must be gone
        expect(container.querySelector("input[type=checkbox]")).toBeNull();

        // A styled span takes its place
        const li = container.querySelector("li");
        const span = li?.querySelector("span");
        expect(span).not.toBeNull();

        const style = span!.getAttribute("style") ?? "";
        expect(style).toContain("background-color: transparent");
        // jsdom may serialize the inherited color keyword either as "currentcolor"
        // or omit it (since it's the default), so just assert the 1px solid border.
        expect(style).toMatch(/border:\s*1px solid/);
        expect(style).toContain("opacity: 0.6");
        // No checkmark image when unchecked
        expect(style).not.toContain("background-image: url");
    });

    test("replaces checked checkbox <input> with filled primary span and embedded check SVG", () => {
        const { container } = renderMd("- [x] Done task");

        expect(container.querySelector("input[type=checkbox]")).toBeNull();

        const span = container.querySelector("li span");
        expect(span).not.toBeNull();

        const style = span!.getAttribute("style") ?? "";
        expect(style).toContain("background-color: var(--primary-wMain)");
        expect(style).toContain("border: 1px solid var(--primary-wMain)");
        expect(style).toContain("opacity: 1");
        expect(style).toContain("background-image: url");
        // Sanity-check the inline checkmark SVG is the one we emit (white fill)
        expect(style).toContain("fill='white'");
    });

    test("drops the disc bullet on a <ul> whose <li>s start with a checkbox", () => {
        const { container } = renderMd("- [ ] one\n- [x] two");

        const ul = container.querySelector("ul");
        expect(ul).not.toBeNull();

        const ulStyle = ul!.getAttribute("style") ?? "";
        expect(ulStyle).toContain("list-style: none");
        // Padding tightened so checkbox aligns near the left edge
        expect(ulStyle).toContain("padding-left: 0.25rem");
    });

    test("renders task <li> as flex with baseline alignment and a small gap", () => {
        const { container } = renderMd("- [ ] hello world");

        const li = container.querySelector("li");
        expect(li).not.toBeNull();

        const liStyle = li!.getAttribute("style") ?? "";
        expect(liStyle).toContain("display: flex");
        expect(liStyle).toContain("align-items: baseline");
        expect(liStyle).toContain("gap: 0.5rem");
    });

    test("preserves the text content next to the checkbox", () => {
        const { getByText } = renderMd("- [ ] write tests\n- [x] ship feature");
        expect(getByText("write tests")).toBeInTheDocument();
        expect(getByText("ship feature")).toBeInTheDocument();
    });

    test("leaves regular bulleted lists untouched (no checkbox = keep disc bullet)", () => {
        const { container } = renderMd("- apple\n- banana");

        const ul = container.querySelector("ul");
        expect(ul).not.toBeNull();
        // No inline style override applied
        expect(ul!.getAttribute("style")).toBeNull();
        expect(container.querySelector("li")?.getAttribute("style")).toBeNull();
    });

    test("only restyles the task-list <ul>, not sibling regular lists", () => {
        // A heading between the two lists prevents marked from merging them.
        const md = ["- regular item", "", "## Tasks", "", "- [ ] task item"].join("\n");
        const { container } = renderMd(md);

        const uls = container.querySelectorAll("ul");
        expect(uls.length).toBe(2);

        // First ul is a plain bulleted list — no inline style override
        expect(uls[0].getAttribute("style")).toBeNull();
        // Second ul is the task list — bullets stripped
        expect(uls[1].getAttribute("style") ?? "").toContain("list-style: none");
    });

    test("handles mixed checked/unchecked items in a single list", () => {
        const { container } = renderMd("- [x] done\n- [ ] todo");

        const spans = container.querySelectorAll("li span");
        expect(spans.length).toBe(2);

        const [first, second] = Array.from(spans).map(s => s.getAttribute("style") ?? "");
        expect(first).toContain("background-color: var(--primary-wMain)");
        expect(first).toContain("background-image: url");

        expect(second).toContain("background-color: transparent");
        expect(second).not.toContain("background-image: url");
    });
});
