import { describe, it, expect } from "vitest";
import { detectMentionTrigger } from "./mentionUtils";

describe("detectMentionTrigger", () => {
    it("returns the query when @ is at the start of the input", () => {
        const text = "@john";
        expect(detectMentionTrigger(text, text.length)).toBe("john");
    });

    it("returns an empty query when only @ has been typed", () => {
        const text = "@";
        expect(detectMentionTrigger(text, text.length)).toBe("");
    });

    it("returns the query when @ is preceded by a space", () => {
        const text = "hello @john";
        expect(detectMentionTrigger(text, text.length)).toBe("john");
    });

    it("returns null when there's no @ before the cursor", () => {
        const text = "hello world";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("returns null when @ is part of a word (e.g. an email)", () => {
        const text = "foo@bar.com";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("returns null when @ is part of an existing internal mention @[...](...)", () => {
        const text = "hello @[John Doe](john@example.com) ";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("allows multi-word queries with a single space", () => {
        const text = "@john du";
        expect(detectMentionTrigger(text, text.length)).toBe("john du");
    });

    it("does not allow more than one space after query", () => {
        const text = "@john  ";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("allows multi-word queries with multiple spaces", () => {
        const text = "@john du doe";
        expect(detectMentionTrigger(text, text.length)).toBe("john du doe");
    });

    it("normalizes non-breaking spaces (U+00A0) to regular spaces", () => {
        // Contenteditable elements often substitute regular spaces with NBSP.
        const text = "@john\u00A0du";
        expect(detectMentionTrigger(text, text.length)).toBe("john du");
    });

    it("treats two consecutive non-breaking spaces as the end of the mention", () => {
        const text = "@john\u00A0\u00A0";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("returns the query with a trailing space", () => {
        const text = "@john ";
        expect(detectMentionTrigger(text, text.length)).toBe("john ");
    });

    it("returns null when the query starts with a space", () => {
        const text = "@ foo";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("returns null when the query contains a newline", () => {
        const text = "@john\nmore text";
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("returns null when the query exceeds 50 characters", () => {
        const longQuery = "a".repeat(51);
        const text = `@${longQuery}`;
        expect(detectMentionTrigger(text, text.length)).toBeNull();
    });

    it("returns the query when it is exactly 50 characters", () => {
        const query = "a".repeat(50);
        const text = `@${query}`;
        expect(detectMentionTrigger(text, text.length)).toBe(query);
    });

    it("uses cursor position to scope the query, ignoring text after the cursor", () => {
        const text = "@john and more";
        // Cursor right after "@john"
        expect(detectMentionTrigger(text, 5)).toBe("john");
    });
});
