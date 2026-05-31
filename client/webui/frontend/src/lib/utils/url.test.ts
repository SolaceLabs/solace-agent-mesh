import { describe, it, expect, afterEach } from "vitest";
import { getHashQueryParams } from "./url";

describe("getHashQueryParams", () => {
    afterEach(() => {
        // Reset both search and hash so cases don't bleed into each other.
        window.history.replaceState({}, "", "/");
    });

    it("parses the query segment that follows the hash route", () => {
        window.history.replaceState({}, "", "/#/chat?agentMode=true&agent=Foo");
        const params = getHashQueryParams();
        expect(params.get("agentMode")).toBe("true");
        expect(params.get("agent")).toBe("Foo");
    });

    it("returns no params when the hash route carries no query", () => {
        window.history.replaceState({}, "", "/#/chat");
        const params = getHashQueryParams();
        expect(params.get("agentMode")).toBeNull();
        expect(params.get("agent")).toBeNull();
    });

    it("ignores a real query string before the hash (reads hash, not search)", () => {
        // This is the whole reason the helper exists: params in window.location.search
        // (the rejected before-# form) must NOT activate Agent Mode.
        window.history.replaceState({}, "", "/?agentMode=true&agent=Foo#/chat");
        expect(window.location.search).toBe("?agentMode=true&agent=Foo"); // precondition
        const params = getHashQueryParams();
        expect(params.get("agentMode")).toBeNull();
        expect(params.get("agent")).toBeNull();
    });
});
