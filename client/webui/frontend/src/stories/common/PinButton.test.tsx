/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { PinButton } from "@/lib/components/common/PinButton";

expect.extend(matchers);

describe("PinButton", () => {
    test("renders with unpinned state (outline star)", () => {
        render(<PinButton isPinned={false} onClick={() => {}} />);

        const button = screen.getByRole("button", { name: "Add to favorites" });
        expect(button).toBeInTheDocument();

        const star = button.querySelector(".lucide-star");
        expect(star).toBeInTheDocument();
        expect(star).toHaveAttribute("fill", "none");
    });

    test("renders with pinned state (filled star)", () => {
        render(<PinButton isPinned={true} onClick={() => {}} />);

        const button = screen.getByRole("button", { name: "Remove from favorites" });
        expect(button).toBeInTheDocument();

        const star = button.querySelector(".lucide-star");
        expect(star).toBeInTheDocument();
        expect(star).toHaveAttribute("fill", "currentColor");
    });

    test("calls onClick when clicked", async () => {
        const user = userEvent.setup();
        const handleClick = vi.fn();

        render(<PinButton isPinned={false} onClick={handleClick} />);

        const button = screen.getByRole("button", { name: "Add to favorites" });
        await user.click(button);

        expect(handleClick).toHaveBeenCalledTimes(1);
    });

    test("does not call onClick when disabled", async () => {
        const user = userEvent.setup();
        const handleClick = vi.fn();

        render(<PinButton isPinned={false} onClick={handleClick} disabled={true} />);

        const button = screen.getByRole("button", { name: "Add to favorites" });
        expect(button).toBeDisabled();

        await user.click(button);
        expect(handleClick).not.toHaveBeenCalled();
    });

    test("shows correct tooltip for unpinned state", () => {
        render(<PinButton isPinned={false} onClick={() => {}} />);
        expect(screen.getByRole("button", { name: "Add to favorites" })).toBeInTheDocument();
    });

    test("shows correct tooltip for pinned state", () => {
        render(<PinButton isPinned={true} onClick={() => {}} />);
        expect(screen.getByRole("button", { name: "Remove from favorites" })).toBeInTheDocument();
    });

    test("applies primary color class when pinned", () => {
        render(<PinButton isPinned={true} onClick={() => {}} />);
        const button = screen.getByRole("button", { name: "Remove from favorites" });
        expect(button.className).toContain("text-(--primary-wMain)");
    });

    test("applies secondary color class when unpinned", () => {
        render(<PinButton isPinned={false} onClick={() => {}} />);
        const button = screen.getByRole("button", { name: "Add to favorites" });
        expect(button.className).toContain("text-(--secondary-text-wMain)");
    });
});
