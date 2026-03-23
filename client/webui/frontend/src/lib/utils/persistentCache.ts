/**
 * IndexedDB-backed persistent cache with an in-memory LRU fast path.
 *
 * Entries survive page refreshes and browser restarts. The in-memory LRU
 * provides synchronous reads for hot entries while IndexedDB handles
 * persistence. Falls back gracefully to memory-only if IndexedDB is
 * unavailable (e.g., private browsing in some browsers).
 *
 * Usage:
 * ```ts
 * const cache = createPersistentCache<string>({
 *     dbName: "artifact-previews",
 *     storeName: "text-snippets",
 *     maxEntries: 500,
 *     ttlMs: 7 * 24 * 60 * 60 * 1000, // 7 days
 * });
 *
 * // Synchronous read from in-memory LRU (returns undefined on miss)
 * const hit = cache.getSync("key");
 *
 * // Async read that checks IndexedDB on memory miss
 * const value = await cache.get("key");
 *
 * // Write (updates both memory and IndexedDB)
 * await cache.set("key", "value");
 * ```
 */

const DB_VERSION = 1;

interface CacheEntry<T> {
    key: string;
    value: T;
    /** Timestamp (ms since epoch) when the entry was written */
    createdAt: number;
    /** Timestamp (ms since epoch) when the entry was last accessed */
    accessedAt: number;
}

export interface PersistentCacheOptions {
    /** IndexedDB database name */
    dbName: string;
    /** IndexedDB object store name */
    storeName: string;
    /** Maximum number of entries to keep. Oldest-accessed entries are evicted. */
    maxEntries: number;
    /** Time-to-live in milliseconds. Entries older than this are treated as expired. 0 = no expiry. */
    ttlMs?: number;
    /** Maximum entries to keep in the in-memory LRU (defaults to maxEntries, capped at 500) */
    memoryMaxEntries?: number;
}

export interface PersistentCache<T> {
    /** Synchronous read from in-memory LRU only. Returns undefined on miss. */
    getSync(key: string): T | undefined;
    /** Async read: checks memory first, then IndexedDB. Returns undefined on miss/expired. */
    get(key: string): Promise<T | undefined>;
    /** Write to both memory and IndexedDB. */
    set(key: string, value: T): Promise<void>;
    /** Delete from both memory and IndexedDB. */
    delete(key: string): Promise<boolean>;
    /** Clear all entries from both memory and IndexedDB. */
    clear(): Promise<void>;
}

/**
 * Open (or create) the IndexedDB database.
 * Returns null if IndexedDB is unavailable.
 */
function openDB(dbName: string, storeName: string): Promise<IDBDatabase | null> {
    return new Promise(resolve => {
        try {
            if (typeof indexedDB === "undefined") {
                resolve(null);
                return;
            }
            const request = indexedDB.open(dbName, DB_VERSION);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains(storeName)) {
                    const store = db.createObjectStore(storeName, { keyPath: "key" });
                    store.createIndex("accessedAt", "accessedAt", { unique: false });
                }
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => {
                console.warn(`[PersistentCache] Failed to open IndexedDB "${dbName}":`, request.error);
                resolve(null);
            };
        } catch {
            // IndexedDB not available (e.g., some privacy modes)
            resolve(null);
        }
    });
}

/**
 * Perform a single IndexedDB transaction operation.
 */
function idbOperation<T>(db: IDBDatabase, storeName: string, mode: IDBTransactionMode, operation: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, mode);
        const store = tx.objectStore(storeName);
        const request = operation(store);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

export function createPersistentCache<T>(options: PersistentCacheOptions): PersistentCache<T> {
    const { dbName, storeName, maxEntries, ttlMs = 0 } = options;
    const memoryMax = Math.min(options.memoryMaxEntries ?? maxEntries, 500);

    // In-memory LRU for synchronous fast path
    const memoryCache = new Map<string, T>();

    // Lazy-initialized IndexedDB connection
    let dbPromise: Promise<IDBDatabase | null> | null = null;

    function getDB(): Promise<IDBDatabase | null> {
        if (!dbPromise) {
            dbPromise = openDB(dbName, storeName);
        }
        return dbPromise;
    }

    function isExpired(entry: CacheEntry<T>): boolean {
        if (ttlMs <= 0) return false;
        return Date.now() - entry.createdAt > ttlMs;
    }

    /** Move key to end of Map (most recently used) */
    function touchMemory(key: string, value: T): void {
        memoryCache.delete(key);
        memoryCache.set(key, value);
        // Evict oldest if over limit
        if (memoryCache.size > memoryMax) {
            const firstKey = memoryCache.keys().next().value;
            if (firstKey !== undefined) memoryCache.delete(firstKey);
        }
    }

    /** Evict oldest entries from IndexedDB if over maxEntries */
    async function evictIfNeeded(db: IDBDatabase): Promise<void> {
        try {
            const count = await idbOperation(db, storeName, "readonly", store => store.count());
            if (count <= maxEntries) return;

            const toEvict = count - maxEntries;
            // Open a cursor on the accessedAt index (ascending = oldest first)
            const tx = db.transaction(storeName, "readwrite");
            const store = tx.objectStore(storeName);
            const index = store.index("accessedAt");
            const request = index.openCursor();
            let evicted = 0;

            await new Promise<void>((resolve, reject) => {
                request.onsuccess = () => {
                    const cursor = request.result;
                    if (cursor && evicted < toEvict) {
                        cursor.delete();
                        evicted++;
                        cursor.continue();
                    } else {
                        resolve();
                    }
                };
                request.onerror = () => reject(request.error);
            });
        } catch (err) {
            console.warn("[PersistentCache] Eviction error:", err);
        }
    }

    return {
        getSync(key: string): T | undefined {
            const value = memoryCache.get(key);
            if (value !== undefined) {
                touchMemory(key, value);
            }
            return value;
        },

        async get(key: string): Promise<T | undefined> {
            // Check memory first
            const memValue = memoryCache.get(key);
            if (memValue !== undefined) {
                touchMemory(key, memValue);
                return memValue;
            }

            // Check IndexedDB
            const db = await getDB();
            if (!db) return undefined;

            try {
                const entry = await idbOperation<CacheEntry<T> | undefined>(db, storeName, "readonly", store => store.get(key));

                if (!entry) return undefined;

                // Check TTL
                if (isExpired(entry)) {
                    // Delete expired entry in background
                    idbOperation(db, storeName, "readwrite", store => store.delete(key)).catch(() => {});
                    return undefined;
                }

                // Promote to memory cache
                touchMemory(key, entry.value);

                // Update accessedAt in background (don't await)
                const updated: CacheEntry<T> = { ...entry, accessedAt: Date.now() };
                idbOperation(db, storeName, "readwrite", store => store.put(updated)).catch(() => {});

                return entry.value;
            } catch {
                return undefined;
            }
        },

        async set(key: string, value: T): Promise<void> {
            // Update memory
            touchMemory(key, value);

            // Update IndexedDB
            const db = await getDB();
            if (!db) return;

            try {
                const now = Date.now();
                const entry: CacheEntry<T> = {
                    key,
                    value,
                    createdAt: now,
                    accessedAt: now,
                };
                await idbOperation(db, storeName, "readwrite", store => store.put(entry));

                // Evict old entries in background
                evictIfNeeded(db).catch(() => {});
            } catch (err) {
                console.warn("[PersistentCache] Write error:", err);
            }
        },

        async delete(key: string): Promise<boolean> {
            const hadMemory = memoryCache.delete(key);

            const db = await getDB();
            if (!db) return hadMemory;

            try {
                await idbOperation(db, storeName, "readwrite", store => store.delete(key));
                return true;
            } catch {
                return hadMemory;
            }
        },

        async clear(): Promise<void> {
            memoryCache.clear();

            const db = await getDB();
            if (!db) return;

            try {
                await idbOperation(db, storeName, "readwrite", store => store.clear());
            } catch (err) {
                console.warn("[PersistentCache] Clear error:", err);
            }
        },
    };
}
