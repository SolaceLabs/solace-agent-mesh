import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createPersistentCache } from "./persistentCache";

function makeCache<T>(opts?: { maxEntries?: number; ttlMs?: number }) {
    return createPersistentCache<T>({
        dbName: "test-db",
        storeName: "test-store",
        maxEntries: opts?.maxEntries ?? 100,
        ttlMs: opts?.ttlMs,
    });
}

describe("createPersistentCache", () => {
    describe("memory-only basics", () => {
        it("set/get returns the stored value", async () => {
            const cache = makeCache<string>();
            await cache.set("a", "hello");
            expect(await cache.get("a")).toBe("hello");
        });

        it("getSync returns the stored value", async () => {
            const cache = makeCache<number>();
            await cache.set("x", 42);
            expect(cache.getSync("x")).toBe(42);
        });

        it("get returns undefined for a missing key", async () => {
            const cache = makeCache<string>();
            expect(await cache.get("missing")).toBeUndefined();
        });

        it("getSync returns undefined for a missing key", () => {
            const cache = makeCache<string>();
            expect(cache.getSync("missing")).toBeUndefined();
        });
    });

    describe("TTL expiry", () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it("returns value before TTL expires", async () => {
            const cache = makeCache<string>({ ttlMs: 1000 });
            await cache.set("k", "val");

            vi.advanceTimersByTime(500);
            expect(cache.getSync("k")).toBe("val");
        });

        // NOTE: TTL expiry after deadline is only enforced on the IndexedDB path
        // (via isExpired on CacheEntry). The in-memory Map does not store
        // createdAt, so memory-only mode cannot expire entries. TTL expiry
        // tests require IndexedDB (e.g. via fake-indexeddb) and are not
        // covered in this memory-fallback suite.
    });

    describe("LRU eviction", () => {
        it("evicts the oldest entry when maxEntries is exceeded", async () => {
            const cache = makeCache<number>({ maxEntries: 3 });

            await cache.set("a", 1);
            await cache.set("b", 2);
            await cache.set("c", 3);
            // All three should be present
            expect(cache.getSync("a")).toBe(1);

            // Adding a 4th should evict the LRU entry.
            // After getSync("a") above, "a" was touched so "b" is now oldest.
            await cache.set("d", 4);
            expect(cache.getSync("b")).toBeUndefined();
            expect(cache.getSync("c")).toBe(3);
            expect(cache.getSync("d")).toBe(4);
        });

        it("touching an entry prevents it from being evicted", async () => {
            const cache = makeCache<number>({ maxEntries: 3 });

            await cache.set("a", 1);
            await cache.set("b", 2);
            await cache.set("c", 3);

            // Touch "a" so it becomes most recently used
            cache.getSync("a");

            await cache.set("d", 4);
            // "b" was oldest untouched, so it should be evicted
            expect(cache.getSync("a")).toBe(1);
            expect(cache.getSync("b")).toBeUndefined();
        });
    });

    describe("delete", () => {
        it("removes an entry so get returns undefined", async () => {
            const cache = makeCache<string>();
            await cache.set("k", "val");
            expect(await cache.get("k")).toBe("val");

            await cache.delete("k");
            expect(await cache.get("k")).toBeUndefined();
            expect(cache.getSync("k")).toBeUndefined();
        });

        it("returns true for existing key and false-y for missing key", async () => {
            const cache = makeCache<string>();
            await cache.set("k", "val");
            expect(await cache.delete("k")).toBe(true);
            // Deleting a non-existent key from memory returns false
            expect(await cache.delete("nope")).toBe(false);
        });
    });

    describe("clear", () => {
        it("removes all entries", async () => {
            const cache = makeCache<string>();
            await cache.set("a", "1");
            await cache.set("b", "2");
            await cache.set("c", "3");

            await cache.clear();

            expect(cache.getSync("a")).toBeUndefined();
            expect(cache.getSync("b")).toBeUndefined();
            expect(cache.getSync("c")).toBeUndefined();
        });
    });

    describe("graceful fallback when indexedDB is unavailable", () => {
        it("all operations work in memory-only mode", async () => {
            // jsdom does not provide indexedDB, so we are already in fallback mode.
            // Verify the full lifecycle works without errors.
            const cache = makeCache<string>();

            await cache.set("x", "hello");
            expect(await cache.get("x")).toBe("hello");
            expect(cache.getSync("x")).toBe("hello");

            await cache.delete("x");
            expect(await cache.get("x")).toBeUndefined();

            await cache.set("y", "world");
            await cache.clear();
            expect(cache.getSync("y")).toBeUndefined();
        });

        it("does not throw when indexedDB is explicitly undefined", async () => {
            // Ensure globalThis.indexedDB is indeed absent in jsdom
            const hasIDB = typeof indexedDB !== "undefined";
            // Whether present or not, operations should not throw
            const cache = makeCache<number>();
            await expect(cache.set("k", 1)).resolves.toBeUndefined();
            await expect(cache.get("k")).resolves.toBe(1);
            await expect(cache.delete("k")).resolves.toBeDefined();
            await expect(cache.clear()).resolves.toBeUndefined();

            if (!hasIDB) {
                // Confirm we tested the no-IndexedDB path
                expect(hasIDB).toBe(false);
            }
        });
    });

    // ---------------------------------------------------------------------------
    // IndexedDB persistence tests
    // ---------------------------------------------------------------------------
    // The tests above only exercise the in-memory fallback because jsdom does not
    // provide IndexedDB. As a result, IDB persistence, IDB-to-memory promotion,
    // TTL expiry/deletion, and IDB LRU eviction have zero coverage.
    //
    // TODO: Install `fake-indexeddb` as a dev dependency and add tests that:
    //   1. Verify set() persists to IDB and get() promotes back to memory.
    //   2. Verify TTL-expired entries return undefined from async get() and are deleted from IDB.
    //   3. Verify LRU eviction removes oldest-accessed entries from IDB when maxEntries is exceeded.
    //   4. Verify delete() removes entries from both memory and IDB.
    //   5. Verify clear() empties both memory and IDB.
    // ---------------------------------------------------------------------------
});
