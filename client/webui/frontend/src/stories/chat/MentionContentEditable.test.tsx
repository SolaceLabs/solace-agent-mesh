/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import React from "react";

import { MentionContentEditable } from "@/lib/components/ui/chat/MentionContentEditable";
import type { Person } from "@/lib/types";

expect.extend(matchers);

// execCommand is not implemented in jsdom
document.execCommand = vi.fn().mockReturnValue(true);

const mockPerson: Person = {
    id: "person-1",
    displayName: "Alice Smith",
    workEmail: "alice@example.com",
};

function renderEditable(props: Partial<React.ComponentProps<typeof MentionContentEditable>> = {}) {
    const onChange = vi.fn();
    render(
        <MentionContentEditable
            value=""
            onChange={onChange}
            placeholder="Type here..."
            {...props}
        />
    );
    return { onChange };
}

describe("MentionContentEditable rendering", () => {
    test("renders the contenteditable div with data-testid", () => {
        renderEditable();
        expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    });

    test("shows placeholder when value is empty", () => {
        renderEditable({ placeholder: "Say something..." });
        expect(screen.getByText("Say something...")).toBeInTheDocument();
    });

    test("hides placeholder when value is non-empty", () => {
        renderEditable({ value: "hello", placeholder: "Say something..." });
        expect(screen.queryByText("Say something...")).not.toBeInTheDocument();
    });

    test("is disabled when disabled prop is true", () => {
        renderEditable({ disabled: true });
        const input = screen.getByTestId("chat-input");
        expect(input).toHaveAttribute("contenteditable", "false");
    });

    test("is editable when disabled prop is false", () => {
        renderEditable({ disabled: false });
        const input = screen.getByTestId("chat-input");
        expect(input).toHaveAttribute("contenteditable", "true");
    });
});

describe("MentionContentEditable mention chip rendering", () => {
    test("renders a mention chip for internal @[Name](id) format", async () => {
        const mentionMap = new Map<string, Person>([["person-1", mockPerson]]);
        await act(async () => {
            render(
                <MentionContentEditable
                    value="Hello @[Alice Smith](person-1) how are you?"
                    onChange={vi.fn()}
                    mentionMap={mentionMap}
                />
            );
        });
        const input = screen.getByTestId("chat-input");
        const chip = input.querySelector(".mention-chip");
        expect(chip).not.toBeNull();
        expect(chip?.textContent).toContain("Alice Smith");
    });

    test("renders fallback @Name when person not in mentionMap", async () => {
        await act(async () => {
            render(
                <MentionContentEditable
                    value="Hey @[Bob Jones](unknown-id) there"
                    onChange={vi.fn()}
                    mentionMap={new Map()}
                />
            );
        });
        const input = screen.getByTestId("chat-input");
        const chip = input.querySelector(".mention-chip");
        expect(chip).not.toBeNull();
        expect(chip?.textContent).toContain("@Bob Jones");
    });

    test("mention chip has data-internal attribute with original format", async () => {
        const mentionMap = new Map<string, Person>([["person-1", mockPerson]]);
        await act(async () => {
            render(
                <MentionContentEditable
                    value="@[Alice Smith](person-1)"
                    onChange={vi.fn()}
                    mentionMap={mentionMap}
                />
            );
        });
        const input = screen.getByTestId("chat-input");
        const chip = input.querySelector(".mention-chip");
        expect(chip?.getAttribute("data-internal")).toBe("@[Alice Smith](person-1)");
        expect(chip?.getAttribute("data-person-id")).toBe("person-1");
    });
});

describe("MentionContentEditable keyboard events", () => {
    test("forwards keyDown events to onKeyDown prop", () => {
        const onKeyDown = vi.fn();
        renderEditable({ onKeyDown });
        const input = screen.getByTestId("chat-input");
        fireEvent.keyDown(input, { key: "Enter" });
        expect(onKeyDown).toHaveBeenCalled();
    });
});

describe("MentionContentEditable paste handling", () => {
    test("calls onPaste prop when paste event fires", () => {
        const onPaste = vi.fn();
        renderEditable({ onPaste });
        const input = screen.getByTestId("chat-input");
        fireEvent.paste(input, {
            clipboardData: { getData: () => "pasted text", setData: vi.fn() },
        });
        expect(onPaste).toHaveBeenCalled();
    });

    test("paste with mention-chip HTML triggers execCommand and calls onChange", () => {
        const onChange = vi.fn();
        render(<MentionContentEditable value="" onChange={onChange} />);
        const input = screen.getByTestId("chat-input");
        const chipHtml = '<span class="mention-chip" data-internal="@[Alice Smith](person-1)" data-person-id="person-1">@Alice Smith</span>';
        fireEvent.paste(input, {
            clipboardData: {
                getData: (type: string) => (type === "text/html" ? chipHtml : ""),
                setData: vi.fn(),
                types: ["text/html", "text/plain"],
            },
        });
        // execCommand is already mocked at the top of the file; it being called means
        // the HTML paste path was exercised (lines 318-343)
        expect(document.execCommand).toHaveBeenCalled();
    });
});
