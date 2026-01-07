import { useWebStorage } from "./useWebStorage";

/**
 * Custom hook that synchronizes a state value with the browser's localStorage.
 * Automatically persists state changes to localStorage and retrieves stored values on mount.
 *
 * @template T - The type of the value to store
 * @param {string} key - The unique key to store the data under in localStorage
 * @param {T} initialValue - The default value to use if the key is not found in localStorage
 * @returns {readonly [T, (value: T | ((val: T) => T)) => void]} A tuple containing the current stored value
 * and a function to update it (supports both direct values and updater functions)
 *
 * @example
 * // Store a simple string value
 * const [username, setUsername] = useLocalStorage('username', 'Guest');
 * // username will be 'Guest' initially, or the stored value if it exists
 * setUsername('John'); // Updates state and localStorage
 *
 * @example
 * // Store an object
 * const [settings, setSettings] = useLocalStorage('app-settings', { theme: 'light', fontSize: 14 });
 * setSettings({ theme: 'dark', fontSize: 16 }); // Replace entire object
 *
 * @example
 * // Use functional updates (like useState)
 * const [count, setCount] = useLocalStorage('counter', 0);
 * setCount(prev => prev + 1); // Increment counter
 *
 * @example
 * // Store an array
 * const [todos, setTodos] = useLocalStorage<string[]>('todos', []);
 * setTodos(prev => [...prev, 'New todo']); // Add item to array
 *
 * @example
 * // Store complex types with TypeScript
 * interface UserPreferences {
 *   theme: 'light' | 'dark';
 *   notifications: boolean;
 * }
 * const [prefs, setPrefs] = useLocalStorage<UserPreferences>('preferences', {
 *   theme: 'light',
 *   notifications: true
 * });
 * setPrefs(prev => ({ ...prev, theme: 'dark' })); // Update specific property
 */
export function useLocalStorage<T>(key: string, initialValue: T) {
    return useWebStorage(key, initialValue, window.localStorage);
}
