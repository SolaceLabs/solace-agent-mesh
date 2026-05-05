/**
 * Tests for the URL-resolution helpers from `@/lib/api/artifacts`.
 * Shared by ChatInputArea, ArtifactsPage, and ArtifactAttachmentCard — a
 * regression in either branch (project vs session) would break cross-context
 * artifact fetches silently.
 */
import { describe, test, expect } from "vitest";

import { type ArtifactWithSession, getArtifactApiUrl, isProjectArtifact } from "@/lib/api/artifacts";

function makeArtifact(overrides: Partial<ArtifactWithSession>): ArtifactWithSession {
    return {
        filename: "file.txt",
        size: 123,
        mime_type: "text/plain",
        last_modified: "2026-01-01T00:00:00Z",
        uri: "",
        sessionId: "session-1",
        sessionName: null,
        ...overrides,
    };
}

describe("isProjectArtifact", () => {
    test("detects modern project-{id} sessionId format", () => {
        expect(isProjectArtifact(makeArtifact({ sessionId: "project-abc123" }))).toBe(true);
    });

    test("detects legacy project:{id} sessionId format", () => {
        expect(isProjectArtifact(makeArtifact({ sessionId: "project:abc123" }))).toBe(true);
    });

    test("detects explicit source === 'project' even when sessionId lacks the prefix", () => {
        expect(isProjectArtifact(makeArtifact({ sessionId: "sess-xyz", source: "project" }))).toBe(true);
    });

    test("returns false for session-only artifacts", () => {
        expect(isProjectArtifact(makeArtifact({ sessionId: "sess-xyz" }))).toBe(false);
        expect(isProjectArtifact(makeArtifact({ sessionId: "sess-xyz", source: "upload" }))).toBe(false);
    });
});

describe("getArtifactApiUrl", () => {
    test("encodes project artifacts with null path segment and project_id query param", () => {
        const url = getArtifactApiUrl(
            makeArtifact({
                sessionId: "project-abc123",
                projectId: "abc123",
                filename: "report final.pdf",
            })
        );
        // null placeholder for session_id path segment, filename URL-encoded,
        // projectId carried via query string.
        expect(url).toBe("/api/v1/artifacts/null/report%20final.pdf?project_id=abc123");
    });

    test("encodes session-only artifacts using sessionId in the path", () => {
        const url = getArtifactApiUrl(
            makeArtifact({
                sessionId: "sess-xyz",
                filename: "notes.md",
            })
        );
        expect(url).toBe("/api/v1/artifacts/sess-xyz/notes.md");
    });

    test("URL-encodes filenames with special characters in the session branch", () => {
        const url = getArtifactApiUrl(
            makeArtifact({
                sessionId: "sess-xyz",
                filename: "with spaces & symbols.txt",
            })
        );
        expect(url).toContain("/api/v1/artifacts/sess-xyz/");
        expect(url).toContain(encodeURIComponent("with spaces & symbols.txt"));
    });

    test("URL-encodes sessionIds with reserved characters in the session branch", () => {
        const url = getArtifactApiUrl(
            makeArtifact({
                sessionId: "sess?weird/id",
                filename: "x.txt",
            })
        );
        // `?` and `/` would otherwise terminate the path segment / start a query.
        expect(url).toBe(`/api/v1/artifacts/${encodeURIComponent("sess?weird/id")}/x.txt`);
    });

    test("falls back to session-path format when source is 'project' but projectId is missing", () => {
        // getArtifactApiUrl only takes the project branch when BOTH
        // isProjectArtifact() is true AND projectId is set.
        const url = getArtifactApiUrl(
            makeArtifact({
                sessionId: "sess-xyz",
                source: "project",
                projectId: undefined,
                filename: "x.txt",
            })
        );
        expect(url).toBe("/api/v1/artifacts/sess-xyz/x.txt");
    });

    test("URL-encodes projectId in the query string", () => {
        const url = getArtifactApiUrl(
            makeArtifact({
                sessionId: "project-abc 123",
                projectId: "abc 123",
                filename: "f.txt",
            })
        );
        expect(url).toBe(`/api/v1/artifacts/null/f.txt?project_id=${encodeURIComponent("abc 123")}`);
    });
});
