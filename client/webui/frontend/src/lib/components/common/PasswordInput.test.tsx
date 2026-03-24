/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { useForm } from "react-hook-form";
import { PasswordInput } from "./PasswordInput";

expect.extend(matchers);

// Wrapper component to use react-hook-form with PasswordInput
const PasswordInputWrapper = ({ showPassword, onToggle, disabled = false }: { showPassword: boolean; onToggle: () => void; disabled?: boolean }) => {
    const { register } = useForm();
    return <PasswordInput name="password" register={register} showPassword={showPassword} onToggle={onToggle} disabled={disabled} />;
};

describe("PasswordInput", () => {
    test("renders input field with password type when showPassword is false", () => {
        render(<PasswordInputWrapper showPassword={false} onToggle={vi.fn()} />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        expect(input).toHaveAttribute("type", "password");
    });

    test("renders input field with text type when showPassword is true", () => {
        render(<PasswordInputWrapper showPassword={true} onToggle={vi.fn()} />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        expect(input).toHaveAttribute("type", "text");
    });

    test("renders toggle button with show icon when password is hidden", () => {
        render(<PasswordInputWrapper showPassword={false} onToggle={vi.fn()} />);
        const button = screen.getByRole("button");
        expect(button).toHaveAttribute("aria-label", "Show password");
    });

    test("renders toggle button with hide icon when password is visible", () => {
        render(<PasswordInputWrapper showPassword={true} onToggle={vi.fn()} />);
        const button = screen.getByRole("button");
        expect(button).toHaveAttribute("aria-label", "Hide password");
    });

    test("calls onToggle when toggle button is clicked", () => {
        const onToggle = vi.fn();
        render(<PasswordInputWrapper showPassword={false} onToggle={onToggle} />);
        const button = screen.getByRole("button");
        button.click();
        expect(onToggle).toHaveBeenCalledOnce();
    });

    test("disables input and button when disabled prop is true", () => {
        render(<PasswordInputWrapper showPassword={false} onToggle={vi.fn()} disabled={true} />);
        const input = screen.getByRole("textbox");
        const button = screen.getByRole("button");
        expect(input).toBeDisabled();
        expect(button).toBeDisabled();
    });

    test("sets autocomplete to new-password", () => {
        render(<PasswordInputWrapper showPassword={false} onToggle={vi.fn()} />);
        const input = screen.getByRole("textbox");
        expect(input).toHaveAttribute("autoComplete", "new-password");
    });
});
