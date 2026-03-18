/**
 * Creates a generic LRU (Least Recently Used) cache with a maximum size.
 *
 * The cache uses a Map to maintain insertion order. When the cache is full,
 * the oldest entry (first item in the Map) is evicted. When an item is accessed,
 * it's moved to the end (most recently used position) by re-inserting it.
 *
 * @param maxSize - Maximum number of entries the cache can hold
 * @returns An object with get, set, has, delete, clear, and size methods
 */
export function createLruCache<T>(maxSize: number) {
    const cache = new Map<string, T>();

    return {
        /**
         * Get a value from the cache and move it to the end (most recently used).
         * Returns undefined if the key doesn't exist.
         */
        get(key: string): T | undefined {
            const value = cache.get(key);
            if (value !== undefined) {
                // Move to end by re-inserting
                cache.delete(key);
                cache.set(key, value);
            }
            return value;
        },

        /**
         * Set a value in the cache. If the cache is full, evicts the oldest entry.
         */
        set(key: string, value: T): void {
            // If key already exists, delete it first to update its position
            if (cache.has(key)) {
                cache.delete(key);
            }
            // If cache is full, remove oldest entry (first item in Map)
            else if (cache.size >= maxSize) {
                const firstKey = cache.keys().next().value;
                if (firstKey !== undefined) {
                    cache.delete(firstKey);
                }
            }
            cache.set(key, value);
        },

        /**
         * Check if a key exists in the cache (does not update LRU order).
         */
        has(key: string): boolean {
            return cache.has(key);
        },

        /**
         * Delete a key from the cache.
         */
        delete(key: string): boolean {
            return cache.delete(key);
        },

        /**
         * Clear all entries from the cache.
         */
        clear(): void {
            cache.clear();
        },

        /**
         * Get the current number of entries in the cache.
         */
        get size(): number {
            return cache.size;
        },
    };
}
