/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ModelDeleteDialog } from "../../lib/components/models";

expect.extend(matchers);

const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onConfirm: vi.fn(),
    modelAlias: "my-custom-model",
    isLoading: false,
};

describe("ModelDeleteDialog - Custom model", () => {
    test("renders delete confirmation dialog with correct title", () => {
        render(<ModelDeleteDialog {...defaultProps} />);
        expect(screen.getByText("Delete Model")).toBeInTheDocument();
    });

    test("shows warning about code-based agents", () => {
        render(<ModelDeleteDialog {...defaultProps} />);
        expect(screen.getByText(/code-based agents/)).toBeInTheDocument();
        expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    });

    test("shows DELETE confirmation label", () => {
        render(<ModelDeleteDialog {...defaultProps} />);
        expect(screen.getByText(/DELETE/)).toBeInTheDocument();
    });

    test("delete button is disabled by default", () => {
        render(<ModelDeleteDialog {...defaultProps} />);
        expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
    });

    test("delete button is enabled after typing DELETE", async () => {
        const user = userEvent.setup();
        render(<ModelDeleteDialog {...defaultProps} />);

        const input = screen.getByRole("textbox");
        await user.type(input, "DELETE");

        expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled();
    });

    test("delete button stays disabled for partial input", async () => {
        const user = userEvent.setup();
        render(<ModelDeleteDialog {...defaultProps} />);

        const input = screen.getByRole("textbox");
        await user.type(input, "DEL");

        expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
    });

    test("delete button stays disabled for wrong case", async () => {
        const user = userEvent.setup();
        render(<ModelDeleteDialog {...defaultProps} />);

        const input = screen.getByRole("textbox");
        await user.type(input, "delete");

        expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
    });

    test("calls onConfirm when delete is confirmed", async () => {
        const onConfirm = vi.fn();
        const user = userEvent.setup();
        render(<ModelDeleteDialog {...defaultProps} onConfirm={onConfirm} />);

        const input = screen.getByRole("textbox");
        await user.type(input, "DELETE");
        await user.click(screen.getByRole("button", { name: "Delete" }));

        expect(onConfirm).toHaveBeenCalledOnce();
    });

    test("input and buttons are disabled when loading", () => {
        render(<ModelDeleteDialog {...defaultProps} isLoading={true} />);

        expect(screen.getByRole("textbox")).toBeDisabled();
        expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    });

    test("input has no placeholder text", () => {
        render(<ModelDeleteDialog {...defaultProps} />);
        const input = screen.getByRole("textbox");
        expect(input).not.toHaveAttribute("placeholder");
    });
});

describe("ModelDeleteDialog - Default model", () => {
    test("shows cannot delete dialog for general model", () => {
        render(<ModelDeleteDialog {...defaultProps} modelAlias="general" />);
        expect(screen.getByText("Cannot Delete Model")).toBeInTheDocument();
        expect(screen.getByText(/General model cannot be deleted/)).toBeInTheDocument();
    });

    test("shows cannot delete dialog for planning model", () => {
        render(<ModelDeleteDialog {...defaultProps} modelAlias="planning" />);
        expect(screen.getByText("Cannot Delete Model")).toBeInTheDocument();
        expect(screen.getByText(/Planning model cannot be deleted/)).toBeInTheDocument();
    });

    test("shows Close button instead of Delete for default models", () => {
        render(<ModelDeleteDialog {...defaultProps} modelAlias="general" />);
        expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    });

    test("does not show text input for default models", () => {
        render(<ModelDeleteDialog {...defaultProps} modelAlias="general" />);
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    test("is case-insensitive for default model check", () => {
        render(<ModelDeleteDialog {...defaultProps} modelAlias="General" />);
        expect(screen.getByText("Cannot Delete Model")).toBeInTheDocument();
    });
});
