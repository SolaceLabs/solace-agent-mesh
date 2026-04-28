/// <reference types="@testing-library/jest-dom" />
import { render } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { MarkdownHTMLConverter } from "@/lib/components/common/MarkdownHTMLConverter";

expect.extend(matchers);

const renderMd = (md: string) => render(<MarkdownHTMLConverter>{md}</MarkdownHTMLConverter>);

describe("MarkdownHTMLConverter — GFM task lists", () => {
    test("keeps the native checkbox input and applies theming + non-interactive attrs (unchecked)", () => {
        const { container } = renderMd("- [ ] Open task");

        const input = container.querySelector("input[type=checkbox]");
        expect(input).not.toBeNull();
        expect(input!.hasAttribute("checked")).toBe(false);

        // `disabled` must be dropped so the browser's accent-color applies;
        // interactivity is suppressed via pointer-events / tabindex / aria.
        expect(input!.hasAttribute("disabled")).toBe(false);
        expect(input!.getAttribute("tabindex")).toBe("-1");
        expect(input!.getAttribute("aria-disabled")).toBe("true");

        const cls = input!.getAttribute("class") ?? "";
        expect(cls).toContain("size-3.5");
        expect(cls).toContain("shrink-0");
        expect(cls).toContain("accent-(--primary-wMain)");
        expect(cls).toContain("pointer-events-none");
    });

    test("keeps the native checkbox input with the checked attribute (checked)", () => {
        const { container } = renderMd("- [x] Done task");

        const input = container.querySelector("input[type=checkbox]");
        expect(input).not.toBeNull();
        expect(input!.hasAttribute("checked")).toBe(true);

        expect(input!.hasAttribute("disabled")).toBe(false);
        expect(input!.getAttribute("tabindex")).toBe("-1");
        expect(input!.getAttribute("aria-disabled")).toBe("true");

        const cls = input!.getAttribute("class") ?? "";
        expect(cls).toContain("accent-(--primary-wMain)");
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

        const inputs = container.querySelectorAll("li input[type=checkbox]");
        expect(inputs.length).toBe(2);

        const [first, second] = Array.from(inputs);
        expect(first.hasAttribute("checked")).toBe(true);
        expect(second.hasAttribute("checked")).toBe(false);

        // Both inputs share the same theming classes regardless of checked state.
        for (const el of [first, second]) {
            expect(el.hasAttribute("disabled")).toBe(false);
            const cls = el.getAttribute("class") ?? "";
            expect(cls).toContain("accent-(--primary-wMain)");
        }
    });
});
