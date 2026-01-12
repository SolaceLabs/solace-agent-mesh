/**
 * @file guards.ts
 * @description Universal type guards and null-checking utilities.
 * Use these functions to narrow types in TypeScript and perform strict existence checks.
 */

/**
 * A type guard that checks if a value is not null or undefined.
 * This is useful for filtering out nullish values from an array or for type narrowing.
 * @param value The value to check.
 * @returns `true` if the value is not `null` and not `undefined`, otherwise `false`.
 */
export function isDefined<T>(value: T | null | undefined): value is T {
    return value !== undefined && value !== null;
}

/**
 * A type guard that checks if a value is null or undefined.
 * This is the inverse of `isDefined`.
 * @param value The value to check.
 * @returns `true` if the value is `null` or `undefined`, otherwise `false`.
 */
export function isNil(value: unknown): value is null | undefined {
    return value === null || value === undefined;
}

/**
 * A type guard that checks if a value is a string.
 * @param value The value to check.
 * @returns `true` if the value is a string, otherwise `false`.
 */
export function isString(value: unknown): value is string {
    return typeof value === "string";
}

/**
 * A type guard that checks if a value is a plain object (not null, not an array).
 * This is useful for distinguishing between objects and other types like arrays or null.
 * @param value The value to check.
 * @returns `true` if the value is a plain object, otherwise `false`.
 */
export function isPlainObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * A type guard that checks if a value is an object (including null).
 * Note: In JavaScript, `typeof null === "object"`, so this returns true for null.
 * For non-null object checks, use `isPlainObject` instead.
 * @param value The value to check.
 * @returns `true` if typeof value is "object", otherwise `false`.
 */
export function isObject(value: unknown): value is object | null {
    return typeof value === "object";
}
