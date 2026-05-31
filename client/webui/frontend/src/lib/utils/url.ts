/**
 * URL utility functions
 */

/**
 * Regex pattern to match HTTP/HTTPS protocol prefix
 */
const PROTOCOL_REGEX = /^https?:\/\//;

/**
 * Extract clean domain from URL
 * Removes protocol (http/https) and www. prefix
 * @param url - The URL to extract domain from
 * @returns The clean domain name
 */
export function getCleanDomain(url: string): string {
    try {
        const domain = url.replace(PROTOCOL_REGEX, "").split("/")[0];
        return domain.startsWith("www.") ? domain.substring(4) : domain;
    } catch {
        return url;
    }
}

/**
 * Get favicon URL from Google's favicon service
 * @param domain - The domain to get favicon for
 * @param size - The size of the favicon (default: 32)
 * @returns The Google favicon service URL
 */
export function getFaviconUrl(domain: string, size: number = 32): string {
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=${size}`;
}

/**
 * Agent Mode params live in the query segment of the hash route, after the
 * route path: `/#/chat?agentMode=true&agent=Foo`. We read them from
 * window.location.hash (not window.location.search) so the URL structure stays
 * identical to v2 (Go), where the same query attaches to a real path:
 * `/chat?agentMode=true&agent=Foo`. Migrating v1→v2 is then just dropping the
 * `#`. Synchronous + read-once-at-load, so no Full-UI flash.
 */
export function getHashQueryParams(): URLSearchParams {
    const hash = window.location.hash;
    const queryIndex = hash.indexOf("?");
    return new URLSearchParams(queryIndex >= 0 ? hash.slice(queryIndex + 1) : "");
}

const POST_LOGIN_REDIRECT_KEY = "sam_post_login_redirect";

/**
 * Remember the current URL before leaving the SPA for the IdP, so the Agent Mode
 * params (which the login round-trip would otherwise drop) can be restored after
 * the callback. Written at every exit-to-login site.
 */
export function stashPostLoginRedirect(): void {
    try {
        localStorage.setItem(POST_LOGIN_REDIRECT_KEY, window.location.href);
    } catch {
        // localStorage unavailable (private mode / disabled) — restore falls back to "/".
    }
}

/**
 * Read and clear the stashed post-login URL. One-shot (deleted on read) and
 * same-origin checked so a poisoned key cannot drive an open redirect. Falls back
 * to "/" when absent, unparseable, or cross-origin.
 */
export function consumePostLoginRedirect(): string {
    let stashed: string | null = null;
    try {
        stashed = localStorage.getItem(POST_LOGIN_REDIRECT_KEY);
        localStorage.removeItem(POST_LOGIN_REDIRECT_KEY);
    } catch {
        return "/";
    }
    if (!stashed) return "/";
    try {
        const url = new URL(stashed);
        if (url.origin === window.location.origin) return url.href;
    } catch {
        // Not an absolute same-origin URL — ignore.
    }
    return "/";
}
