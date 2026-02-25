import { cva } from "class-variance-authority";

// Style constants
export const HOVER_BG = "hover:bg-[var(--color-background-w100)]";
export const ACTIVE_BG = "bg-[var(--color-background-w100)]";

// CVA style definitions for navigation components
export const navButtonStyles = cva(["flex", "h-10", "cursor-pointer", "items-center", "transition-colors", "py-6", "w-full", HOVER_BG], {
    variants: {
        variant: {
            expanded: "justify-start pr-4 pl-6 text-sm font-normal",
            collapsed: "justify-center p-0",
            bottom: "justify-center p-2 text-[var(--color-primary-text-w10)]",
        },
        active: {
            true: ACTIVE_BG,
            false: "",
        },
        indent: {
            true: "pl-4",
            false: "",
        },
    },
    defaultVariants: { variant: "expanded", active: false, indent: false },
});

export const iconWrapperStyles = cva(["flex", "size-8", "items-center", "justify-center", "rounded"], {
    variants: {
        active: {
            true: `border border-[var(--color-brand-w60)] ${ACTIVE_BG}`,
            false: "",
        },
        withMargin: {
            true: "mr-2",
            false: "",
        },
    },
    defaultVariants: { active: false, withMargin: false },
});

export const iconStyles = cva(["size-6"], {
    variants: {
        active: {
            true: "text-[var(--color-brand-w60)]",
            false: "text-[var(--color-secondary-text-w50)]",
        },
        muted: {
            true: "text-[var(--color-primary-text-w10)]",
            false: "",
        },
    },
    defaultVariants: { active: false, muted: false },
});

export const navTextStyles = cva([], {
    variants: {
        active: {
            true: "font-bold text-white",
            false: "text-[var(--color-secondary-text-w50)]",
        },
    },
    defaultVariants: { active: false },
});
