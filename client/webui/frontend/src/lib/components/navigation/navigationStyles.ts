import { cva } from "class-variance-authority";

export const HOVER_BG = "hover:bg-(--nav-bgActive)";
export const ACTIVE_BG = "bg-(--nav-bgActive)";

export const navButtonStyles = cva(["flex", "h-10", "cursor-pointer", "items-center", "transition-colors", "py-6", "w-full", HOVER_BG], {
    variants: {
        variant: {
            expanded: "justify-start pr-4 pl-6 text-sm font-normal",
            collapsed: "justify-center p-0",
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
            true: `border border-(--nav-accentLight) ${ACTIVE_BG}`,
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
            true: "text-(--nav-accentLight)",
            false: "text-(--nav-textMuted)",
        },
        muted: {
            true: "text-(--nav-text)",
            false: "",
        },
    },
    defaultVariants: { active: false, muted: false },
});

export const navTextStyles = cva([], {
    variants: {
        active: {
            true: "font-bold text-(--nav-text)",
            false: "text-(--nav-textMuted)",
        },
    },
    defaultVariants: { active: false },
});
