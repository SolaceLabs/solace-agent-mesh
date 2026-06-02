import { describe, it, expect, afterEach } from "vitest";
import { getHashQueryParams, getHashPath, stashPostLoginRedirect, consumePostLoginRedirect } from "./url";

const POST_LOGIN_REDIRECT_KEY = "sam_post_login_redirect";

describe("getHashQueryParams", () => {
    afterEach(() => {
        // Reset both search and hash so cases don't bleed into each other.
        window.history.replaceState({}, "", "/");
    });

    it("parses the query segment that follows the hash route", () => {
        window.history.replaceState({}, "", "/#/embed/chat?agent=Foo");
        const params = getHashQueryParams();
        expect(params.get("agent")).toBe("Foo");
    });

    it("returns no params when the hash route carries no query", () => {
        window.history.replaceState({}, "", "/#/embed/chat");
        const params = getHashQueryParams();
        expect(params.get("agent")).toBeNull();
    });

    it("ignores a real query string before the hash (reads hash, not search)", () => {
        // Params in window.location.search (the rejected before-# form) must not be read —
        // the embedded surface's ?agent= travels with the hash route.
        window.history.replaceState({}, "", "/?agent=Foo#/embed/chat");
        expect(window.location.search).toBe("?agent=Foo"); // precondition
        expect(getHashQueryParams().get("agent")).toBeNull();
    });
});

describe("getHashPath", () => {
    afterEach(() => {
        window.history.replaceState({}, "", "/");
    });

    it("returns the route path without the leading # or query segment", () => {
        window.history.replaceState({}, "", "/#/embed/chat?agent=Foo");
        expect(getHashPath()).toBe("/embed/chat");
    });

    it("returns the path when there is no query", () => {
        window.history.replaceState({}, "", "/#/chat");
        expect(getHashPath()).toBe("/chat");
    });

    it("returns empty string when there is no hash", () => {
        window.history.replaceState({}, "", "/");
        expect(getHashPath()).toBe("");
    });
});

describe("post-login redirect stash/restore", () => {
    afterEach(() => {
        localStorage.removeItem(POST_LOGIN_REDIRECT_KEY);
        window.history.replaceState({}, "", "/");
    });

    it("stashes the current URL and restores it once", () => {
        window.history.replaceState({}, "", "/#/embed/chat?agent=Foo");
        stashPostLoginRedirect();
        expect(localStorage.getItem(POST_LOGIN_REDIRECT_KEY)).toContain("/embed/chat");

        const restored = consumePostLoginRedirect();
        expect(restored).toContain("/#/embed/chat?agent=Foo");
    });

    it("is one-shot — the key is cleared after the first read", () => {
        window.history.replaceState({}, "", "/#/embed/chat?agent=Foo");
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
        localStorage.setItem(POST_LOGIN_REDIRECT_KEY, "https://evil.example.com/#/embed/chat?agent=Foo");
        expect(consumePostLoginRedirect()).toBe("/");
    });

    it("rejects an unparseable stashed value", () => {
        localStorage.setItem(POST_LOGIN_REDIRECT_KEY, "not-a-url");
        expect(consumePostLoginRedirect()).toBe("/");
    });
});
