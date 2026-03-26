import { describe, test, expect } from "vitest";
import { shareKeys } from "@/lib/api/share/keys";

describe("shareKeys", () => {
    test("all is the base key", () => {
        expect(shareKeys.all).toEqual(["shares"]);
    });

    test("links() extends all with 'link'", () => {
        expect(shareKeys.links()).toEqual(["shares", "link"]);
    });

    test("link(sessionId) extends links with session id", () => {
        expect(shareKeys.link("sess-123")).toEqual(["shares", "link", "sess-123"]);
    });

    test("lists() extends all with 'list'", () => {
        expect(shareKeys.lists()).toEqual(["shares", "list"]);
    });

    test("list() without filters extends lists with undefined filters", () => {
        expect(shareKeys.list()).toEqual(["shares", "list", { filters: undefined }]);
    });

    test("list(filters) extends lists with filters object", () => {
        const filters = { page: 1, pageSize: 10, search: "hello" };
        expect(shareKeys.list(filters)).toEqual(["shares", "list", { filters }]);
    });

    test("users(shareId) extends all with 'users' and share id", () => {
        expect(shareKeys.users("share-abc")).toEqual(["shares", "users", "share-abc"]);
    });

    test("sharedWithMe() extends all with 'shared-with-me'", () => {
        expect(shareKeys.sharedWithMe()).toEqual(["shares", "shared-with-me"]);
    });

    test("view(shareId) extends all with 'view' and share id", () => {
        expect(shareKeys.view("share-xyz")).toEqual(["shares", "view", "share-xyz"]);
    });
});
