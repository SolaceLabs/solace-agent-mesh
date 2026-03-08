/* eslint-disable react-refresh/only-export-components */
import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { Slot } from "@radix-ui/react-slot";
import { Controller, FormProvider, useFormContext, useFormState } from "react-hook-form";
import type { FieldValues, FieldPath, ControllerProps } from "react-hook-form";
import { cn } from "@/lib/utils/index";
import { Label } from "@/lib/components/ui/label";

const Form = FormProvider;

type FormFieldContextValue<TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>> = {
    name: TName;
};

const FormFieldContext = React.createContext<FormFieldContextValue>({} as FormFieldContextValue);

const FormField = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({ ...props }: ControllerProps<TFieldValues, TName>) => {
    const memoizedFieldName = React.useMemo(() => ({ name: props.name }), [props.name]);

    return (
        <FormFieldContext.Provider value={memoizedFieldName}>
            <Controller {...props} />
        </FormFieldContext.Provider>
    );
};

const useFormField = () => {
    const fieldContext = React.useContext(FormFieldContext);
    const itemContext = React.useContext(FormItemContext);
    const { getFieldState } = useFormContext();
    const formState = useFormState({ name: fieldContext.name });
    const fieldState = getFieldState(fieldContext.name, formState);

    if (!fieldContext) {
        throw new Error("useFormField should be used within <FormField>");
    }

    const { id } = itemContext;

    return {
        id,
        name: fieldContext.name,
        formItemId: `${id}-form-item`,
        formDescriptionId: `${id}-form-item-description`,
        formMessageId: `${id}-form-item-message`,
        ...fieldState,
    };
};

type FormItemContextValue = {
    id: string;
};

const FormItemContext = React.createContext<FormItemContextValue>({} as FormItemContextValue);

function FormItem({ className, ...props }: React.ComponentProps<"div">) {
    const id = React.useId();
    const memoizedItemId = React.useMemo(() => ({ id }), [id]);

    return (
        <FormItemContext.Provider value={memoizedItemId}>
            <div data-slot="form-item" className={cn("grid gap-2", className)} {...props} />
        </FormItemContext.Provider>
    );
}

function FormLabel({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
    const { error, formItemId } = useFormField();

    return <Label data-slot="form-label" data-error={!!error} className={cn("data-[error=true]:text-(--color-error-wMain)", className)} htmlFor={formItemId} {...props} />;
}

function FormControl({ ...props }: React.ComponentProps<typeof Slot>) {
    const { error, formItemId, formDescriptionId, formMessageId } = useFormField();

    return <Slot data-slot="form-control" id={formItemId} aria-describedby={!error ? `${formDescriptionId}` : `${formDescriptionId} ${formMessageId}`} aria-invalid={!!error} {...props} />;
}

function FormDescription({ className, ...props }: React.ComponentProps<"p">) {
    const { formDescriptionId } = useFormField();

    return <p data-slot="form-description" id={formDescriptionId} className={cn("text-muted-foreground text-sm", className)} {...props} />;
}

function FormError({ className, ...props }: React.ComponentProps<"p">) {
    const { error, formMessageId } = useFormField();

    if (!error) return null;

    const body = String(error?.message ?? "");

    return (
        <p data-slot="form-error" id={formMessageId} className={cn("text-xs text-(--color-error-wMain)", className)} {...props}>
            {body}
        </p>
    );
}

function FormInputLabel({ className, rightAlign, ...props }: React.ComponentProps<"p"> & { rightAlign?: boolean }) {
    const { formMessageId } = useFormField();
    if (!props.children) return null;
    return (
        <p data-slot="form-input-label" id={formMessageId} className={cn("text-muted-foreground text-xs", rightAlign && "text-right", className)} {...props}>
            {props.children}
        </p>
    );
}

export { useFormField, Form, FormItem, FormLabel, FormControl, FormDescription, FormError, FormInputLabel, FormField };
