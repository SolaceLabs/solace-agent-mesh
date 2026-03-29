/**
 * Shared styling constants for chat bubbles
 * Ensures consistent appearance between regular chat and shared/read-only views
 */

export const CHAT_BUBBLE_TEXT_STYLES = "text-base" as const;

export const CHAT_BUBBLE_MESSAGE_STYLES = {
    text: "text-base leading-relaxed",
    paragraph: "text-base leading-relaxed whitespace-pre-wrap",
} as const;
