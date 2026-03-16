import { cva } from "class-variance-authority";

export const classForIconButton = cva(["h-8", "w-8", "p-0", "text-(--secondary-text-wMain)", "hover:text-(--primary-text-wMain)"]);

export const classForEmptyMessage = cva(["text-center", "text-sm", "text-(--secondary-text-wMain)"], {
    variants: {
        size: {
            default: "py-8",
            compact: "p-4",
        },
    },
    defaultVariants: { size: "default" },
});
