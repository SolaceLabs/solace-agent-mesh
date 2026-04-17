import type { Session } from "@/lib/types";

/** Coerce any of {null, epoch-ms number, epoch-ms digit-string, ISO-8601 string} to epoch-ms. */
const toEpochMs = (v: string | number | null | undefined): number => {
    if (v == null) return Number.NaN;
    if (typeof v === "number") return v;
    const n = Number(v);
    if (Number.isFinite(n)) return n;
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
