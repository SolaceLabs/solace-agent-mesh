import { useWebStorage } from "./useWebStorage";

/**
 * Custom hook that synchronizes a state value with the browser's sessionStorage.
 * Automatically persists state changes to sessionStorage and retrieves stored values on mount.
 * Data persists only for the current browser session and is cleared when the tab/window is closed.
 *
 * @template T - The type of the value to store
 * @param {string} key - The unique key to store the data under in sessionStorage
 * @param {T} initialValue - The default value to use if the key is not found in sessionStorage
 * @returns {readonly [T, (value: T | ((val: T) => T)) => void]} A tuple containing the current stored value
 * and a function to update it (supports both direct values and updater functions)
 *
 * @example
 * // Store temporary form data during a session
 * const [formData, setFormData] = useSessionStorage('checkout-form', { email: '', address: '' });
 * setFormData({ email: 'user@example.com', address: '123 Main St' });
 *
 * @example
 * // Store authentication token for current session
 * const [token, setToken] = useSessionStorage('auth-token', null);
 * setToken('abc123'); // Token cleared when tab closes
 *
 * @example
 * // Use functional updates
 * const [stepNumber, setStepNumber] = useSessionStorage('wizard-step', 1);
 * setStepNumber(prev => prev + 1); // Move to next step
 *
 * @example
 * // Store temporary shopping cart
 * const [cart, setCart] = useSessionStorage<string[]>('temp-cart', []);
 * setCart(prev => [...prev, 'item-123']); // Add item
 *
 * @example
 * // Store complex types with TypeScript
 * interface WizardState {
 *   currentStep: number;
 *   completedSteps: number[];
 * }
 * const [wizard, setWizard] = useSessionStorage<WizardState>('wizard-state', {
 *   currentStep: 1,
 *   completedSteps: []
 * });
 * setWizard(prev => ({ ...prev, currentStep: 2 }));
 */
export function useSessionStorage<T>(key: string, initialValue: T) {
    return useWebStorage(key, initialValue, window.sessionStorage);
}
