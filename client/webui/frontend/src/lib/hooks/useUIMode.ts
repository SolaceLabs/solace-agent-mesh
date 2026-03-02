import { useLocation } from "react-router-dom";

/**
 * Detects if the app is in "onboard" mode via `?mode=onboard` query param.
 * In onboard mode the sidebar, session panel, and activity side panel are hidden
 * to present a simplified full-width chat experience.
 */
export function useUIMode() {
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const isOnboardMode = searchParams.get("mode") === "onboard";
    return { isOnboardMode };
}
