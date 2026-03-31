/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ModelSetupDialog } from "@/lib/components/models/ModelSetupDialog";

expect.extend(matchers);

function renderDialog(props: { open: boolean; hasWritePermissions: boolean; onOpenChange?: (open: boolean) => void }) {
    const onOpenChange = props.onOpenChange ?? vi.fn();
    return {
        onOpenChange,
        ...render(
            <MemoryRouter>
                <ModelSetupDialog open={props.open} onOpenChange={onOpenChange} hasWritePermissions={props.hasWritePermissions} />
            </MemoryRouter>
        ),
    };
}

describe("ModelSetupDialog", () => {
    describe("with write permissions (admin)", () => {
        test("renders admin title and buttons", () => {
            renderDialog({ open: true, hasWritePermissions: true });

            expect(screen.getByText("Set Up Your Default LLM Models")).toBeInTheDocument();
            expect(screen.getByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
            expect(screen.getByRole("button", { name: /Skip for Now/i })).toBeInTheDocument();
        });

        test("does not show Close button", () => {
            renderDialog({ open: true, hasWritePermissions: true });

            expect(screen.queryByRole("button", { name: /^Close$/i })).not.toBeInTheDocument();
        });

        test("Skip for Now calls onOpenChange(false)", async () => {
            const onOpenChange = vi.fn();
            renderDialog({ open: true, hasWritePermissions: true, onOpenChange });

            await userEvent.click(screen.getByRole("button", { name: /Skip for Now/i }));

            expect(onOpenChange).toHaveBeenCalledWith(false);
        });

        test("Add Model calls onOpenChange(false)", async () => {
            const onOpenChange = vi.fn();
            renderDialog({ open: true, hasWritePermissions: true, onOpenChange });

            await userEvent.click(screen.getByRole("button", { name: /Go to Models/i }));

            expect(onOpenChange).toHaveBeenCalledWith(false);
        });
    });

    describe("without write permissions (non-admin)", () => {
        test("renders non-admin title and Close button", () => {
            renderDialog({ open: true, hasWritePermissions: false });

            expect(screen.getByText("No Default LLM Models Available")).toBeInTheDocument();
            expect(screen.getByText(/Contact an administrator/)).toBeInTheDocument();
            expect(screen.getByRole("button", { name: /Close/i })).toBeInTheDocument();
        });

        test("does not show Add Model or Skip for Now buttons", () => {
            renderDialog({ open: true, hasWritePermissions: false });

            expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
            expect(screen.queryByRole("button", { name: /Skip for Now/i })).not.toBeInTheDocument();
        });

        test("Close calls onOpenChange(false)", async () => {
            const onOpenChange = vi.fn();
            renderDialog({ open: true, hasWritePermissions: false, onOpenChange });

            await userEvent.click(screen.getByRole("button", { name: /Close/i }));

            expect(onOpenChange).toHaveBeenCalledWith(false);
        });
    });

    test("does not render dialog content when closed", () => {
        renderDialog({ open: false, hasWritePermissions: true });

        expect(screen.queryByText("Set Up Your Default LLM Models")).not.toBeInTheDocument();
    });
});
