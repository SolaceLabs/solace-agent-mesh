import { describe, it, expect, afterEach } from "vitest";
import { getHashQueryParams, stashPostLoginRedirect, consumePostLoginRedirect } from "./url";

const POST_LOGIN_REDIRECT_KEY = "sam_post_login_redirect";

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

describe("post-login redirect stash/restore", () => {
    afterEach(() => {
        localStorage.removeItem(POST_LOGIN_REDIRECT_KEY);
        window.history.replaceState({}, "", "/");
    });

    it("stashes the current URL and restores it once", () => {
        window.history.replaceState({}, "", "/#/chat?agentMode=true&agent=Foo");
        stashPostLoginRedirect();
        expect(localStorage.getItem(POST_LOGIN_REDIRECT_KEY)).toContain("agentMode=true");

        const restored = consumePostLoginRedirect();
        expect(restored).toContain("/#/chat?agentMode=true&agent=Foo");
    });

    it("is one-shot — the key is cleared after the first read", () => {
        window.history.replaceState({}, "", "/#/chat?agentMode=true&agent=Foo");
        stashPostLoginRedirect();

        consumePostLoginRedirect();
        expect(localStorage.getItem(POST_LOGIN_REDIRECT_KEY)).toBeNull();
        // A second consume has nothing to restore and falls back to "/".
        expect(consumePostLoginRedirect()).toBe("/");
    });

    it("falls back to / when nothing was stashed", () => {
        expect(consumePostLoginRedirect()).toBe("/");
    });

    it("rejects a cross-origin stashed value (open-redirect guard)", () => {
        localStorage.setItem(POST_LOGIN_REDIRECT_KEY, "https://evil.example.com/#/chat?agentMode=true");
        expect(consumePostLoginRedirect()).toBe("/");
    });

    it("rejects an unparseable stashed value", () => {
        localStorage.setItem(POST_LOGIN_REDIRECT_KEY, "not-a-url");
        expect(consumePostLoginRedirect()).toBe("/");
    });
});
