/// <reference types="@testing-library/jest-dom" />
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

import { CHAT_BUBBLE_TEXT_STYLES, CHAT_BUBBLE_MESSAGE_STYLES } from "@/lib/components/ui/chat/chat-bubble-styles";

describe("chat-bubble-styles", () => {
    test("CHAT_BUBBLE_TEXT_STYLES is a non-empty string", () => {
        expect(typeof CHAT_BUBBLE_TEXT_STYLES).toBe("string");
        expect(CHAT_BUBBLE_TEXT_STYLES.length).toBeGreaterThan(0);
    });

    test("CHAT_BUBBLE_TEXT_STYLES includes text-base", () => {
        expect(CHAT_BUBBLE_TEXT_STYLES).toBe("text-base");
    });

    test("CHAT_BUBBLE_MESSAGE_STYLES has text property", () => {
        expect(CHAT_BUBBLE_MESSAGE_STYLES.text).toBeDefined();
        expect(typeof CHAT_BUBBLE_MESSAGE_STYLES.text).toBe("string");
    });

    test("CHAT_BUBBLE_MESSAGE_STYLES has paragraph property", () => {
        expect(CHAT_BUBBLE_MESSAGE_STYLES.paragraph).toBeDefined();
        expect(typeof CHAT_BUBBLE_MESSAGE_STYLES.paragraph).toBe("string");
    });

    test("CHAT_BUBBLE_MESSAGE_STYLES.text includes text-base and leading-relaxed", () => {
        expect(CHAT_BUBBLE_MESSAGE_STYLES.text).toContain("text-base");
        expect(CHAT_BUBBLE_MESSAGE_STYLES.text).toContain("leading-relaxed");
    });

    test("CHAT_BUBBLE_MESSAGE_STYLES.paragraph includes whitespace-pre-wrap", () => {
        expect(CHAT_BUBBLE_MESSAGE_STYLES.paragraph).toContain("whitespace-pre-wrap");
    });

    test("CHAT_BUBBLE_MESSAGE_STYLES.paragraph includes text-base and leading-relaxed", () => {
        expect(CHAT_BUBBLE_MESSAGE_STYLES.paragraph).toContain("text-base");
        expect(CHAT_BUBBLE_MESSAGE_STYLES.paragraph).toContain("leading-relaxed");
    });

    test("CHAT_BUBBLE_MESSAGE_STYLES is a frozen/const object with exactly text and paragraph keys", () => {
        const keys = Object.keys(CHAT_BUBBLE_MESSAGE_STYLES);
        expect(keys).toEqual(expect.arrayContaining(["text", "paragraph"]));
        expect(keys).toHaveLength(2);
    });
});
