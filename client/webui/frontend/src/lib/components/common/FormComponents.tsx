import { useMemo } from "react";
import { Controller, type UseFormRegister, type UseFormTrigger, type Control } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { PageLabel, ErrorLabel } from "./PageCommon";

// ============================================================================
// TYPES
// ============================================================================

type FormError = { message?: string };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFormRegister = UseFormRegister<any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFormControl = Control<any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFormTrigger = UseFormTrigger<any>;

export interface PasswordInputProps {
    name: string;
    label: string;
    register: AnyFormRegister;
    error?: FormError;
    showPassword: boolean;
    onToggle: () => void;
    helpText?: string;
    placeholder?: string;
    disabled?: boolean;
    required?: boolean;
}

export interface FormFieldProps {
    label: string;
    required?: boolean;
    error?: FormError;
    warning?: string;
    helpText?: string;
    statusIndicator?: React.ReactNode;
    children: React.ReactNode;
}

export interface TextInputProps {
    name: string;
    label: string;
    register: AnyFormRegister;
    error?: FormError;
    warning?: string;
    required?: boolean;
    helpText?: string;
    disabled?: boolean;
    statusIndicator?: React.ReactNode;
    onBlur?: () => void;
    type?: "text" | "number";
    inputMode?: "decimal";
    step?: number;
    min?: number;
    max?: number;
}

export interface SelectOption {
    value: string;
    label: string;
    description?: string;
}

export interface SelectFieldProps {
    name: string;
    label: string;
    control: AnyFormControl;
    options: SelectOption[];
    error?: FormError;
    required?: boolean;
    trigger?: AnyFormTrigger;
    onValueChange?: (value: string) => void;
}

// ============================================================================
// REUSABLE COMPONENTS
// ============================================================================

/**
 * Reusable form field wrapper with label, error, and warning handling
 */
export const FormField = ({ label, required = false, error, warning, helpText, statusIndicator, children }: FormFieldProps) => (
    <div className="grid grid-rows-[auto_1fr] gap-2">
        <div className="flex items-start justify-between gap-2">
            <PageLabel required={required}>{label}</PageLabel>
            {statusIndicator}
        </div>
        <div className="flex flex-col gap-1">
            {children}
            {(error || warning || helpText) && (
                <div className="mt-1">
                    {error && <ErrorLabel>{error.message}</ErrorLabel>}
                    {warning && <div className="text-xs text-yellow-600">{warning}</div>}
                    {helpText && <div className="text-secondary-foreground text-xs">{helpText}</div>}
                </div>
            )}
        </div>
    </div>
);

/**
 * Reusable password input with show/hide toggle
 * Button is positioned inside the input field
 */
export const PasswordInput = ({ name, label, register, error, showPassword, onToggle, helpText, placeholder, disabled = false, required = true }: PasswordInputProps) => (
    <FormField label={label} required={required} error={error} helpText={helpText}>
        <div className="relative">
            <input
                {...register(name)}
                type={showPassword ? "text" : "password"}
                placeholder={placeholder}
                autoComplete="new-password"
                disabled={disabled}
                className={`w-full rounded border px-3 py-2 pr-10 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${error ? "border-red-500" : "border-gray-300"}`}
            />
            <button
                type="button"
                onClick={onToggle}
                disabled={disabled}
                title={showPassword ? "Hide password" : "Show password"}
                className="text-secondary-foreground hover:text-primary-text absolute top-1/2 right-2 -translate-y-1/2 p-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
        </div>
    </FormField>
);

/**
 * Reusable text/number input field with optional validation
 */
export const TextInput = ({ name, label, register, error, warning, required = false, helpText, disabled = false, statusIndicator, onBlur, type = "text", inputMode, step, min, max }: TextInputProps) => {
    const registerOptions: Record<string, unknown> = {
        required: required ? `${label} is required` : false,
    };

    // Add number validation if type is number
    if (type === "number") {
        if (min !== undefined) {
            registerOptions.min = {
                value: min,
                message: `${label} must be at least ${min}`,
            };
        }
        if (max !== undefined) {
            registerOptions.max = {
                value: max,
                message: `${label} must not exceed ${max}`,
            };
        }
    }

    return (
        <FormField label={label} required={required} error={error} warning={warning} helpText={helpText} statusIndicator={statusIndicator}>
            <input
                {...register(name, registerOptions)}
                type={type}
                inputMode={inputMode}
                step={type === "number" ? step : undefined}
                autoComplete="off"
                disabled={disabled}
                onBlur={onBlur}
                className={`w-full rounded border px-3 py-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${error ? "border-red-500" : "border-gray-300"}`}
            />
        </FormField>
    );
};

/**
 * Reusable select field with descriptions
 */
export const SelectField = ({ name, label, control, options, error, required = false, trigger, onValueChange }: SelectFieldProps) => {
    const labelMap = useMemo(() => {
        return options.reduce((acc, opt) => ({ ...acc, [opt.value]: opt.label }), {} as Record<string, string>);
    }, [options]);

    return (
        <FormField label={label} required={required} error={error}>
            <Controller
                name={name}
                control={control}
                render={({ field }) => (
                    <Select
                        value={field.value || ""}
                        onValueChange={value => {
                            field.onChange(value);
                            onValueChange?.(value);
                            trigger?.(name);
                        }}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue>{field.value ? labelMap[field.value] : undefined}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {options.map(option => (
                                <SelectItem key={option.value} value={option.value}>
                                    <div className="flex flex-col">
                                        <div>{option.label}</div>
                                        {option.description && <div className="text-muted-foreground text-xs">{option.description}</div>}
                                    </div>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                )}
            />
        </FormField>
    );
};
