export const NODE_COLORS = {
    user: "text-(--accent-n3-wMain)",
    switch: "text-(--accent-n3-wMain)",
    group: "text-(--accent-n3-wMain)",

    llm: "text-(--accent-n2-wMain)",
    loop: "text-(--accent-n2-wMain)",

    tool: "text-(--accent-n7-wMain)",
    peer: "text-(--accent-n5-wMain)",

    artifact: "text-(--accent-n1-wMain)",
    map: "text-(--accent-n1-wMain)",
    mapLabel: "text-(--accent-n1-w100)",
} as const;

/** Accent color for numeric values, version badges, and case labels */
export const NODE_ACCENT_COLOR = "text-(--accent-n3-wMain)";

export const ARTIFACT_CARD_STYLES = {
    border: "border-(--accent-n1-w30)",
    bg: "bg-(--accent-n1-w10)",
    text: "text-(--accent-n1-wMain)",
    textHover: "hover:text-(--accent-n1-w100) hover:underline",
    badgeBg: "bg-(--accent-n1-w20)",
} as const;

export const PEER_BADGE_STYLES = {
    bg: "bg-(--accent-n3-w10)",
    text: "text-(--accent-n3-wMain)",
} as const;
