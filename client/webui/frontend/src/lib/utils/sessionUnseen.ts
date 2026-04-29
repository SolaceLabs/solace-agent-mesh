import type { Session } from "@/lib/types";

/**
 * Coerce any of {null, epoch-ms/epoch-s number, digit-string, ISO-8601 string}
 * to epoch-ms. Numeric values smaller than ~year-2286 in ms (i.e. typical
 * epoch-seconds) are multiplied by 1000.
 */
export const toEpochMs = (v: string | number | null | undefined): number => {
    if (v == null) return Number.NaN;
    if (typeof v === "number") return v < 10000000000 ? v * 1000 : v;
    const n = Number(v);
    if (Number.isFinite(n)) return n < 10000000000 ? n * 1000 : n;
    const parsed = Date.parse(v);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
};

/**
 * Session has updates the user hasn't opened yet.
 *
 * `lastViewedAt` is an epoch-ms int from the server; `updatedTime` and
 * `createdTime` come back as ISO strings (BaseTimestampResponse converts
 * them). Both sides are normalized before comparing. A null `lastViewedAt`
 * means "never viewed" — we baseline to created_time so sessions with no
 * activity beyond creation don't show a dot.
 */
export const hasUnseenUpdates = (session: Session): boolean => {
    const updated = toEpochMs(session.updatedTime);
    const baseline = session.lastViewedAt ?? toEpochMs(session.createdTime);
    return Number.isFinite(updated) && Number.isFinite(baseline) && updated > baseline;
};
