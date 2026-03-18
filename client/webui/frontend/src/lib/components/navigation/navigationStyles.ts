import { cva } from "class-variance-authority";

export const HOVER_BG = "hover:bg-(--darkSurface-bgActive)";
export const ACTIVE_BG = "bg-(--darkSurface-bgActive)";

export const navButtonStyles = cva(["flex", "h-10", "cursor-pointer", "items-center", "justify-start", "transition-colors", "py-6", "w-full", "pl-4", "pr-4", "text-sm", "font-normal", HOVER_BG], {
    variants: {
        active: {
            true: ACTIVE_BG,
            false: "",
        },
        indent: {
            true: "pl-4",
            false: "",
        },
    },
    defaultVariants: { active: false, indent: false },
});

export const iconWrapperStyles = cva(["flex", "size-8", "items-center", "justify-center", "rounded"], {
    variants: {
        active: {
            true: `border border-(--darkSurface-brandAccent) ${ACTIVE_BG}`,
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
            true: "text-(--brand-w60)",
            false: "text-(--darkSurface-textMuted)",
        },
        muted: {
            true: "text-(--darkSurface-text)",
            false: "",
        },
    },
    defaultVariants: { active: false, muted: false },
});

export const navTextStyles = cva([], {
    variants: {
        active: {
            true: "font-bold text-(--darkSurface-text)",
            false: "text-(--darkSurface-textMuted)",
        },
    },
    defaultVariants: { active: false },
});
