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
