import { useBooleanFlagValue } from "@openfeature/react-sdk";

export function useIsNewNavigationEnabled(): boolean {
    return useBooleanFlagValue("new_navigation", false);
}
