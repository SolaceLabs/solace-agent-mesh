import { v4 as uuidv4 } from "uuid";

// Forces uuid to use the crypto.getRandomValues() fallback instead of crypto.randomUUID().
// crypto.randomUUID() is undefined outside secure contexts (HTTPS/localhost) and throws
// when the app is served over plain HTTP, which is supported in some SAM deployments.
// Passing any options (even {}) bypasses uuid's native.randomUUID() shortcut.
export const uuid = (): string => uuidv4({});
