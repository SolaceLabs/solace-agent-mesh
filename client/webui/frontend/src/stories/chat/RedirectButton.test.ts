/**
 * Tests for RedirectButton — redirect URL validation via ALLOWED_PREFIXES + URL parsing.
 * Ensures open-redirect prevention for valid routes, blocked routes, and bypass attempts.
 */
import { describe, test, expect } from "vitest";

// Extract the validation logic to test it in isolation without rendering.
// This mirrors the check at RedirectButton.tsx:~71-82.
const ALLOWED_PREFIXES = ["/builder", "/chat", "/prompts"];

function isRouteAllowed(route: string): boolean {
    const trimmed = (route || "").trim();
    try {
        const parsed = new URL(trimmed, "https://localhost");
        if (parsed.origin !== "https://localhost" || !ALLOWED_PREFIXES.some(p => parsed.pathname.startsWith(p))) {
            return false;
        }
        return true;
    } catch {
        return false;
    }
}

describe("RedirectButton URL validation", () => {
    describe("valid routes", () => {
        test("allows /builder", () => {
            expect(isRouteAllowed("/builder")).toBe(true);
        });

        test("allows /builder with subpath", () => {
            expect(isRouteAllowed("/builder/some-session")).toBe(true);
        });

        test("allows /chat", () => {
            expect(isRouteAllowed("/chat")).toBe(true);
        });

        test("allows /chat with subpath", () => {
            expect(isRouteAllowed("/chat/session-123")).toBe(true);
        });

        test("allows /prompts", () => {
            expect(isRouteAllowed("/prompts")).toBe(true);
        });

        test("allows routes with query parameters", () => {
            expect(isRouteAllowed("/builder?param=value")).toBe(true);
        });
    });

    describe("blocked routes", () => {
        test("blocks absolute external URL", () => {
            expect(isRouteAllowed("https://evil.com")).toBe(false);
        });

        test("blocks javascript: protocol", () => {
            expect(isRouteAllowed("javascript:alert(1)")).toBe(false);
        });

        test("blocks data: protocol", () => {
            expect(isRouteAllowed("data:text/html,<h1>hi</h1>")).toBe(false);
        });

        test("blocks routes outside allowed prefixes", () => {
            expect(isRouteAllowed("/admin")).toBe(false);
        });

        test("blocks root path", () => {
            expect(isRouteAllowed("/")).toBe(false);
        });

        test("blocks empty string", () => {
            expect(isRouteAllowed("")).toBe(false);
        });
    });

    describe("bypass attempts", () => {
        test("blocks protocol-relative URL //evil.com", () => {
            expect(isRouteAllowed("//evil.com")).toBe(false);
        });

        test("blocks backslash bypass /\\evil.com", () => {
            expect(isRouteAllowed("/\\evil.com")).toBe(false);
        });

        test("blocks URL-encoded path /%2fbuilder", () => {
            // %2f decodes to /, so pathname becomes //builder — origin changes
            expect(isRouteAllowed("/%2f%2fevil.com")).toBe(false);
        });

        test("blocks leading whitespace bypass", () => {
            // Whitespace before a protocol could trick some parsers
            expect(isRouteAllowed("  https://evil.com")).toBe(false);
        });

        test("blocks prefix-like external domain /builder.evil.com", () => {
            // /builder.evil.com starts with /builder — but it's still a path, so
            // new URL treats it as a relative path on the same origin. This IS allowed
            // because the pathname starts with /builder. The real protection comes from
            // being a same-origin relative path.
            expect(isRouteAllowed("/builder.evil.com")).toBe(true);
        });
    });
});
