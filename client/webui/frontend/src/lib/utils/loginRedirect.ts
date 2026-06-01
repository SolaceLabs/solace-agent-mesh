/**
 * Build the login URL, preserving the destination the user was trying to reach.
 *
 * The OAuth login flow navigates away from the app and back, which would
 * otherwise drop the current `?agent=...` selection and `#/chat` route. We
 * append the current `search + hash` as an encoded `redirect_path` so the
 * backend can carry it through the round-trip and the auth callback can restore
 * it. When there is nothing to preserve, the login URL is returned unchanged.
 *
 * @param loginUrl - The configured external login URL.
 * @param search - `window.location.search` (e.g. `?agent=X`).
 * @param hash - `window.location.hash` (e.g. `#/chat`).
 */
export function buildLoginUrl(loginUrl: string, search: string, hash: string): string {
    const destination = `${search}${hash}`;
    if (!destination) {
        return loginUrl;
    }
    const separator = loginUrl.includes("?") ? "&" : "?";
    return `${loginUrl}${separator}redirect_path=${encodeURIComponent(destination)}`;
}