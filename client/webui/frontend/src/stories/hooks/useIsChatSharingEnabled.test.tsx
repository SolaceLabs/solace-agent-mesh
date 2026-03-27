/**
 * Tests for useIsChatSharingEnabled hook — feature flag check for chat sharing.
 */
import React from "react";
import { renderHook } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import type { ConfigContextValue } from "@/lib/contexts/ConfigContext";
import { useIsChatSharingEnabled } from "@/lib/hooks/useIsChatSharingEnabled";

/** Minimal ConfigContextValue with required fields defaulted. */
function makeConfigValue(overrides: Partial<ConfigContextValue> = {}): ConfigContextValue {
    return {
        webuiServerUrl: "",
        platformServerUrl: "",
        configAuthLoginUrl: "",
        configUseAuthorization: false,
        configWelcomeMessage: "",
        configRedirectUrl: "",
        configCollectFeedback: false,
        configBotName: "",
        configLogoUrl: "",
        frontend_use_authorization: false,
        platformConfigured: false,
        identityServiceType: null,
        ...overrides,
    };
}

function createWrapper(configValue: ConfigContextValue) {
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <ConfigContext.Provider value={configValue}>{children}</ConfigContext.Provider>;
    };
}

describe("useIsChatSharingEnabled", () => {
    test("returns false when configFeatureEnablement is undefined", () => {
        const config = makeConfigValue({ configFeatureEnablement: undefined });
        const { result } = renderHook(() => useIsChatSharingEnabled(), {
            wrapper: createWrapper(config),
        });

        expect(result.current).toBe(false);
    });

    test("returns false when chatSharing is not set in feature enablement", () => {
        const config = makeConfigValue({ configFeatureEnablement: {} });
        const { result } = renderHook(() => useIsChatSharingEnabled(), {
            wrapper: createWrapper(config),
        });

        expect(result.current).toBe(false);
    });

    test("returns false when chatSharing is false", () => {
        const config = makeConfigValue({
            configFeatureEnablement: { chatSharing: false },
        });
        const { result } = renderHook(() => useIsChatSharingEnabled(), {
            wrapper: createWrapper(config),
        });

        expect(result.current).toBe(false);
    });

    test("returns true when chatSharing is true", () => {
        const config = makeConfigValue({
            configFeatureEnablement: { chatSharing: true },
        });
        const { result } = renderHook(() => useIsChatSharingEnabled(), {
            wrapper: createWrapper(config),
        });

        expect(result.current).toBe(true);
    });
});
