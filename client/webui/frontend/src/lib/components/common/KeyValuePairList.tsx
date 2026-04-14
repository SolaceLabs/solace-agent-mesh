import { useFieldArray, useFormContext } from "react-hook-form";
import { X } from "lucide-react";
import { Button, Input } from "@/lib/components/ui";
import { ErrorLabel } from "./ErrorLabel";

interface KeyValuePairListProps {
    name: string;
    minPairs?: number;
    error?: unknown;
    emptyMessage?: string;
    onChange?: () => void;
}

/**
 * Reusable component for managing key-value pair inputs in forms.
 * Uses react-hook-form's useFieldArray for dynamic array management.
 *
 * @param name - Field path for react-hook-form
 * @param minPairs - Minimum number of pairs to show (default: 1)
 * @param error - Form validation error for this field
 */
export const KeyValuePairList = ({ name, minPairs = 1, error, emptyMessage = "No items added yet", onChange }: KeyValuePairListProps) => {
    const { control, register } = useFormContext();
    const { fields, remove } = useFieldArray({
        control,
        name,
    });

    // Safely extract error message
    const getErrorMessage = (): string | undefined => {
        if (!error || typeof error !== "object") return undefined;
        const errObj = error as Record<string, unknown>;
        if (errObj.root && typeof errObj.root === "object") {
            const rootErr = errObj.root as Record<string, unknown>;
            if (typeof rootErr.message === "string") return rootErr.message;
        }
        if (typeof errObj.message === "string") return errObj.message;
        return undefined;
    };

    const errorMessage = getErrorMessage();

    return (
        <div className="space-y-2">
            {fields.length === 0 && <div className="rounded-lg bg-(--secondary-w10) p-3 text-sm text-(--secondary-text-wMain) italic">{emptyMessage}</div>}
            {fields.map((field, index) => (
                <div key={field.id} className="grid grid-cols-[1fr_1fr_auto] items-start gap-2">
                    <div>
                        {index === 0 && <div className="mb-1 text-sm">Key</div>}
                        <Input {...register(`${name}.${index}.key`)} type="text" aria-label={`Key ${index + 1}`} onBlur={onChange} />
                    </div>
                    <div>
                        {index === 0 && <div className="mb-1 text-sm">Value</div>}
                        <Input {...register(`${name}.${index}.value`)} type="text" aria-label={`Value ${index + 1}`} onBlur={onChange} />
                    </div>
                    <div className="flex items-center" style={{ paddingTop: index === 0 ? "24px" : "0" }}>
                        {fields.length > minPairs && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                tooltip="Remove pair"
                                tooltipSide="right"
                                onClick={() => {
                                    remove(index);
                                    onChange?.();
                                }}
                            >
                                <X className="size-4" />
                            </Button>
                        )}
                    </div>
                </div>
            ))}
            {errorMessage && <ErrorLabel message={errorMessage} />}
        </div>
    );
};
