import { useState } from "react";

/**
 * Internal hook that provides a shared implementation for web storage hooks.
 * This should not be used directly - use useLocalStorage or useSessionStorage instead.
 *
 * @internal
 */
export function useWebStorage<T>(key: string, initialValue: T, storage: Storage) {
    const [storedValue, setStoredValue] = useState<T>(() => {
        if (typeof window === "undefined") {
            return initialValue;
        }
        try {
            const item = storage.getItem(key);
            if (item) {
                return JSON.parse(item);
            } else {
                storage.setItem(key, JSON.stringify(initialValue));
                return initialValue;
            }
        } catch (error) {
            console.warn(`Error reading storage key "${key}":`, error);
            return initialValue;
        }
    });

    const setValue = (value: T | ((val: T) => T)) => {
        try {
            setStoredValue(prevValue => {
                const valueToStore = value instanceof Function ? value(prevValue) : value;

                if (typeof window !== "undefined") {
                    storage.setItem(key, JSON.stringify(valueToStore));
                }

                return valueToStore;
            });
        } catch (error) {
            console.warn(`Error setting storage key "${key}":`, error);
        }
    };

    return [storedValue, setValue] as const;
}
