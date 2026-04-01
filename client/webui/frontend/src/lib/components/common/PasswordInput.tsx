import { useState } from "react";
import { Controller } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import type { Control, FieldValues, Path } from "react-hook-form";

import { Button, Input } from "@/lib/components/ui";

export interface PasswordInputProps<T extends FieldValues = FieldValues> {
    name: Path<T>;
    control: Control<T>;
    hasStoredValue?: boolean;
    placeholder?: string;
    disabled?: boolean;
    rules?: Record<string, unknown>;
}

const STORED_VALUE_PLACEHOLDER = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";

/**
 * Password input with show/hide toggle.
 *
 * When `hasStoredValue` is true and the field is empty, an asterisk placeholder
 * is shown to indicate a credential exists server-side. The eye toggle is always
 * visible (signals a sensitive field) but is inert when only the placeholder is shown.
 */
export const PasswordInput = <T extends FieldValues = FieldValues>({
    name,
    control,
    hasStoredValue = false,
    placeholder,
    disabled = false,
    rules,
}: PasswordInputProps<T>) => {
    const [showPassword, setShowPassword] = useState(false);

    return (
        <Controller
            name={name}
            control={control}
            rules={rules}
            render={({ field }) => {
                const hasUserInput = !!field.value;
                const isEyeFunctional = hasUserInput || !hasStoredValue;
                const effectivePlaceholder = hasStoredValue && !hasUserInput ? STORED_VALUE_PLACEHOLDER : placeholder;
                const inputType = showPassword && isEyeFunctional ? "text" : "password";

                return (
                    <div className="relative">
                        <Input
                            {...field}
                            value={field.value ?? ""}
                            type={inputType}
                            placeholder={effectivePlaceholder}
                            autoComplete="new-password"
                            disabled={disabled}
                            className="pr-10"
                            role="textbox"
                        />
                        <Button
                            type="button"
                            onClick={() => {
                                if (isEyeFunctional) {
                                    setShowPassword(prev => !prev);
                                }
                            }}
                            disabled={disabled}
                            variant="ghost"
                            size="sm"
                            className="pointer-events-auto absolute top-1/2 right-1 -translate-y-1/2"
                            title={showPassword && isEyeFunctional ? "Hide password" : "Show password"}
                            aria-label={showPassword && isEyeFunctional ? "Hide password" : "Show password"}
                        >
                            {showPassword && isEyeFunctional ? <EyeOff size={18} /> : <Eye size={18} />}
                        </Button>
                    </div>
                );
            }}
        />
    );
};
