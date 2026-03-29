import { describe, test, expect, vi, beforeEach } from "vitest";
import type * as ServiceModule from "@/lib/api/share/service";

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPatch = vi.fn();
const mockDelete = vi.fn();

describe("share service", () => {
    let service: typeof ServiceModule;

    beforeEach(async () => {
        vi.resetModules();
        mockGet.mockReset();
        mockPost.mockReset();
        mockPatch.mockReset();
        mockDelete.mockReset();

        vi.doMock("@/lib/api/client", () => ({
            api: {
                webui: {
                    get: mockGet,
                    post: mockPost,
                    patch: mockPatch,
                    delete: mockDelete,
                },
            },
        }));

        service = await import("@/lib/api/share/service");
    });

    // ── getShareLinkForSession ──────────────────────────────────────

    describe("getShareLinkForSession", () => {
        test("returns camelCased share link when found", async () => {
            const fakeResponse = {
                ok: true,
                status: 200,
                json: vi.fn().mockResolvedValue({
                    share_id: "s1",
                    session_id: "sess1",
                    created_at: "2025-01-01",
                }),
            };
            mockGet.mockResolvedValue(fakeResponse);

            const result = await service.getShareLinkForSession("sess1");

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share/link/sess1", { fullResponse: true });
            expect(result).toEqual({
                shareId: "s1",
                sessionId: "sess1",
                createdAt: "2025-01-01",
            });
        });

        test("returns null when server responds with 404", async () => {
            const fakeResponse = { ok: false, status: 404 };
            mockGet.mockResolvedValue(fakeResponse);

            const result = await service.getShareLinkForSession("not-found");

            expect(result).toBeNull();
        });

        test("throws when server responds with non-404 error", async () => {
            const fakeResponse = {
                ok: false,
                status: 500,
                json: vi.fn().mockResolvedValue({ detail: "Server error" }),
            };
            mockGet.mockResolvedValue(fakeResponse);

            await expect(service.getShareLinkForSession("sess1")).rejects.toThrow("Server error");
        });

        test("throws with default message when error json parsing fails", async () => {
            const fakeResponse = {
                ok: false,
                status: 500,
                json: vi.fn().mockRejectedValue(new Error("parse error")),
            };
            mockGet.mockResolvedValue(fakeResponse);

            await expect(service.getShareLinkForSession("sess1")).rejects.toThrow("Failed to get share link");
        });
    });

    // ── getShareUsers ───────────────────────────────────────────────

    describe("getShareUsers", () => {
        test("calls GET with correct URL and returns camelCased response", async () => {
            mockGet.mockResolvedValue({ users: [{ user_email: "a@b.com", permission_level: "read" }] });

            const result = await service.getShareUsers("share-1");

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share/share-1/users");
            expect(result).toEqual({ users: [{ userEmail: "a@b.com", permissionLevel: "read" }] });
        });
    });

    // ── createShareLink ─────────────────────────────────────────────

    describe("createShareLink", () => {
        test("calls POST and returns camelCased share link", async () => {
            mockPost.mockResolvedValue({ share_id: "new-share", session_id: "sess2" });

            const result = await service.createShareLink("sess2", { require_authentication: true });

            expect(mockPost).toHaveBeenCalledWith("/api/v1/share/sess2", { require_authentication: true });
            expect(result).toEqual({ shareId: "new-share", sessionId: "sess2" });
        });

        test("uses empty options object by default", async () => {
            mockPost.mockResolvedValue({ share_id: "s" });

            await service.createShareLink("sess3");

            expect(mockPost).toHaveBeenCalledWith("/api/v1/share/sess3", {});
        });
    });

    // ── deleteShareLink ─────────────────────────────────────────────

    describe("deleteShareLink", () => {
        test("calls DELETE with correct URL", async () => {
            mockDelete.mockResolvedValue(undefined);

            await service.deleteShareLink("share-del");

            expect(mockDelete).toHaveBeenCalledWith("/api/v1/share/share-del");
        });
    });

    // ── addShareUsers ───────────────────────────────────────────────

    describe("addShareUsers", () => {
        test("calls POST with users payload and returns camelCased response", async () => {
            const payload = { shares: [{ user_email: "x@y.com", access_level: "RESOURCE_VIEWER" }] };
            mockPost.mockResolvedValue({ added: [{ user_email: "x@y.com" }] });

            const result = await service.addShareUsers("share-a", payload);

            expect(mockPost).toHaveBeenCalledWith("/api/v1/share/share-a/users", payload);
            expect(result).toEqual({ added: [{ userEmail: "x@y.com" }] });
        });
    });

    // ── deleteShareUsers ────────────────────────────────────────────

    describe("deleteShareUsers", () => {
        test("calls DELETE with body and returns camelCased response on success", async () => {
            const payload = { user_emails: ["a@b.com"] };
            const fakeResponse = {
                ok: true,
                json: vi.fn().mockResolvedValue({ removed: ["a@b.com"] }),
            };
            mockDelete.mockResolvedValue(fakeResponse);

            const result = await service.deleteShareUsers("share-b", payload);

            expect(mockDelete).toHaveBeenCalledWith(
                "/api/v1/share/share-b/users",
                expect.objectContaining({
                    fullResponse: true,
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                })
            );
            expect(result).toEqual({ removed: ["a@b.com"] });
        });

        test("throws when response is not ok", async () => {
            const payload = { user_emails: ["a@b.com"] };
            const fakeResponse = {
                ok: false,
                json: vi.fn().mockResolvedValue({ detail: "Not allowed" }),
            };
            mockDelete.mockResolvedValue(fakeResponse);

            await expect(service.deleteShareUsers("share-b", payload)).rejects.toThrow("Not allowed");
        });

        test("throws default message when error json parsing fails", async () => {
            const payload = { user_emails: ["a@b.com"] };
            const fakeResponse = {
                ok: false,
                json: vi.fn().mockRejectedValue(new Error("parse")),
            };
            mockDelete.mockResolvedValue(fakeResponse);

            await expect(service.deleteShareUsers("share-b", payload)).rejects.toThrow("Failed to delete share users");
        });
    });

    // ── listSharedWithMe ────────────────────────────────────────────

    describe("listSharedWithMe", () => {
        test("calls GET and returns camelCased list", async () => {
            mockGet.mockResolvedValue([{ share_id: "s1", session_title: "My Chat", shared_by_email: "owner@test.com" }]);

            const result = await service.listSharedWithMe();

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share/shared-with-me");
            expect(result).toEqual([{ shareId: "s1", sessionTitle: "My Chat", sharedByEmail: "owner@test.com" }]);
        });
    });

    // ── forkSharedChat ──────────────────────────────────────────────

    describe("forkSharedChat", () => {
        test("calls POST to fork endpoint and returns camelCased response", async () => {
            mockPost.mockResolvedValue({ session_id: "forked-sess", share_id: "s1" });

            const result = await service.forkSharedChat("s1");

            expect(mockPost).toHaveBeenCalledWith("/api/v1/share/s1/fork");
            expect(result).toEqual({ sessionId: "forked-sess", shareId: "s1" });
        });
    });

    // ── viewSharedSession ───────────────────────────────────────────

    describe("viewSharedSession", () => {
        test("calls GET with credentials and returns camelCased session view", async () => {
            mockGet.mockResolvedValue({
                share_id: "s1",
                session_title: "Shared Session",
                chat_history: [],
            });

            const result = await service.viewSharedSession("s1");

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share/s1", { credentials: "include" });
            expect(result).toEqual({
                shareId: "s1",
                sessionTitle: "Shared Session",
                chatHistory: [],
            });
        });
    });

    // ── downloadSharedArtifact ──────────────────────────────────────

    describe("downloadSharedArtifact", () => {
        test("calls GET with fullResponse and returns blob on success", async () => {
            const fakeBlob = new Blob(["data"], { type: "application/pdf" });
            const fakeResponse = {
                ok: true,
                blob: vi.fn().mockResolvedValue(fakeBlob),
            };
            mockGet.mockResolvedValue(fakeResponse);

            const result = await service.downloadSharedArtifact("s1", "report.pdf");

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share/s1/artifacts/report.pdf", {
                fullResponse: true,
                credentials: "include",
            });
            expect(result).toBe(fakeBlob);
        });

        test("encodes the filename in the URL", async () => {
            const fakeBlob = new Blob(["data"]);
            const fakeResponse = {
                ok: true,
                blob: vi.fn().mockResolvedValue(fakeBlob),
            };
            mockGet.mockResolvedValue(fakeResponse);

            await service.downloadSharedArtifact("s1", "my file (1).pdf");

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share/s1/artifacts/my%20file%20(1).pdf", expect.any(Object));
        });

        test("throws when response is not ok", async () => {
            const fakeResponse = {
                ok: false,
                statusText: "Not Found",
            };
            mockGet.mockResolvedValue(fakeResponse);

            await expect(service.downloadSharedArtifact("s1", "missing.pdf")).rejects.toThrow("Failed to download: Not Found");
        });
    });

    // ── updateShareLink ─────────────────────────────────────────────

    describe("updateShareLink", () => {
        test("calls PATCH and returns camelCased result", async () => {
            mockPatch.mockResolvedValue({ share_id: "s1", is_active: true });

            const result = await service.updateShareLink("s1", { require_authentication: true });

            expect(mockPatch).toHaveBeenCalledWith("/api/v1/share/s1", { require_authentication: true });
            expect(result).toEqual({ shareId: "s1", isActive: true });
        });
    });

    // ── listShareLinks ──────────────────────────────────────────────

    describe("listShareLinks", () => {
        test("calls GET without query params when none provided", async () => {
            mockGet.mockResolvedValue({ items: [], total: 0 });

            await service.listShareLinks();

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share");
        });

        test("appends query params when provided", async () => {
            mockGet.mockResolvedValue({ items: [], total: 0 });

            await service.listShareLinks({ page: 2, pageSize: 25, search: "test" });

            expect(mockGet).toHaveBeenCalledWith("/api/v1/share?page=2&pageSize=25&search=test");
        });
    });

    // ── updateShareSnapshot ─────────────────────────────────────────

    describe("updateShareSnapshot", () => {
        test("calls POST with user email body and returns camelCased result", async () => {
            mockPost.mockResolvedValue({ snapshot_time: 1700000000 });

            const result = await service.updateShareSnapshot("s1", "user@test.com");

            expect(mockPost).toHaveBeenCalledWith("/api/v1/share/s1/update-snapshot", {
                user_email: "user@test.com",
            });
            expect(result).toEqual({ snapshotTime: 1700000000 });
        });

        test("calls POST without body when no email provided", async () => {
            mockPost.mockResolvedValue({ snapshot_time: 1700000000 });

            await service.updateShareSnapshot("s1");

            expect(mockPost).toHaveBeenCalledWith("/api/v1/share/s1/update-snapshot", undefined);
        });
    });
});
