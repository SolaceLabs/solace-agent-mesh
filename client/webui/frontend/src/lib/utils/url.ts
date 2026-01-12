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
