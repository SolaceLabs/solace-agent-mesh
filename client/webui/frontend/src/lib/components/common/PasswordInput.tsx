import { Eye, EyeOff } from "lucide-react";
import type { UseFormRegister } from "react-hook-form";

import { Button, Input } from "@/lib/components/ui";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFormRegister = UseFormRegister<any>;

export interface PasswordInputProps {
    name: string;
    register: AnyFormRegister;
    showPassword: boolean;
    onToggle: () => void;
    placeholder?: string;
    disabled?: boolean;
}

/**
 * Password input with show/hide toggle
 * Button is positioned inside the input field
 */
export const PasswordInput = ({ name, register, showPassword, onToggle, placeholder, disabled = false }: PasswordInputProps) => (
    <div className="relative">
        <Input {...register(name)} type={showPassword ? "text" : "password"} placeholder={placeholder} autoComplete="new-password" disabled={disabled} className="pr-10" />
        <Button
            type="button"
            onClick={onToggle}
            disabled={disabled}
            variant="ghost"
            size="sm"
            className="pointer-events-auto absolute top-1/2 right-1 -translate-y-1/2"
            title={showPassword ? "Hide password" : "Show password"}
            aria-label={showPassword ? "Hide password" : "Show password"}
        >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
        </Button>
    </div>
);
