/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { PromptImportDialog } from "@/lib/components/prompts";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// Blob.text() is not implemented in jsdom 27 — polyfill via FileReader
if (typeof Blob.prototype.text === "undefined") {
    Object.defineProperty(Blob.prototype, "text", {
        value: function (this: Blob) {
            return new Promise<string>((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result as string);
                reader.onerror = () => reject(reader.error);
                reader.readAsText(this);
            });
        },
    });
}

const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onImport: vi.fn().mockResolvedValue(undefined),
    existingPrompts: [],
};

function renderDialog(
    props: Partial<React.ComponentProps<typeof PromptImportDialog>> = {}
) {
    return render(
        <StoryProvider>
            <PromptImportDialog {...defaultProps} {...props} />
        </StoryProvider>
    );
}

function makePromptFile(command?: string) {
    const data = {
        version: "1.0",
        exportedAt: Date.now(),
        prompt: {
            name: "Test Prompt",
            promptText: "Some prompt text",
            ...(command !== undefined ? { command } : {}),
        },
    };
    return new File([JSON.stringify(data)], "prompt.json", { type: "application/json" });
}

function makeFileList(file: File): FileList {
    return Object.assign([file], {
        item: (i: number) => (i === 0 ? file : null),
    }) as unknown as FileList;
}

async function uploadFile(file: File) {
    const input = document.querySelector('input[name="promptFile"]') as HTMLInputElement;
    await act(async () => {
        Object.defineProperty(input, "files", {
            value: makeFileList(file),
            configurable: true,
        });
        fireEvent.change(input);
    });
}

beforeEach(() => {
    vi.clearAllMocks();
});

describe("PromptImportDialog command validation", () => {
    test("shows editable command input when imported command has invalid characters", async () => {
        renderDialog();
        await uploadFile(makePromptFile("bad command!"));

        const commandInput = await screen.findByRole("textbox", { name: /chat shortcut/i });
        expect(commandInput).toBeInTheDocument();
    });

    test("Import button is disabled when imported command has invalid characters", async () => {
        renderDialog();
        await uploadFile(makePromptFile("bad command!"));

        await waitFor(() => {
            expect(screen.getByTestId("dialogConfirmButton")).toBeDisabled();
        });
    });

    test("Import button becomes enabled after correcting an invalid command", async () => {
        renderDialog();
        await uploadFile(makePromptFile("bad command!"));

        const commandInput = await screen.findByRole("textbox", { name: /chat shortcut/i });
        await act(async () => {
            fireEvent.change(commandInput, { target: { value: "valid-cmd" } });
        });

        await waitFor(() => {
            expect(screen.getByTestId("dialogConfirmButton")).not.toBeDisabled();
        });
    });

    test("valid command is displayed as read-only text, not an input", async () => {
        renderDialog();
        await uploadFile(makePromptFile("valid-cmd"));

        await waitFor(() => {
            expect(
                screen.queryByRole("textbox", { name: /chat shortcut/i })
            ).not.toBeInTheDocument();
            expect(screen.getByText("valid-cmd")).toBeInTheDocument();
        });
    });

    test("Import button is enabled when imported command is valid", async () => {
        renderDialog();
        await uploadFile(makePromptFile("valid-cmd"));

        await waitFor(() => {
            expect(screen.getByTestId("dialogConfirmButton")).not.toBeDisabled();
        });
    });
});
