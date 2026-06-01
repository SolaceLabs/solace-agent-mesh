import { describe, expect, it } from "vitest";

import { buildLoginUrl } from "./loginRedirect";

describe("buildLoginUrl", () => {
    it("appends the current search + hash as an encoded redirect_path", () => {
        const url = buildLoginUrl("https://host/api/v1/auth/login", "?agent=JDE_HR_Agent", "#/chat");
        expect(url).toBe(`https://host/api/v1/auth/login?redirect_path=${encodeURIComponent("?agent=JDE_HR_Agent#/chat")}`);
    });

    it("uses & when the login URL already has a query string", () => {
        const url = buildLoginUrl("https://host/login?foo=bar", "?agent=X", "");
        expect(url).toBe(`https://host/login?foo=bar&redirect_path=${encodeURIComponent("?agent=X")}`);
    });

    it("returns the login URL unchanged when there is no destination to preserve", () => {
        expect(buildLoginUrl("https://host/login", "", "")).toBe("https://host/login");
    });

    it("preserves a hash-only destination", () => {
        const url = buildLoginUrl("https://host/login", "", "#/chat");
        expect(url).toBe(`https://host/login?redirect_path=${encodeURIComponent("#/chat")}`);
    });
});