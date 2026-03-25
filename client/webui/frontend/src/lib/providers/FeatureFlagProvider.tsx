import { useEffect, type ReactNode } from "react";
import { OpenFeature, OpenFeatureProvider } from "@openfeature/react-sdk";
import { api } from "../api";
import { SamFeatureProvider } from "./openfeature";

interface FeatureFlagInfo {
    key: string;
    name: string;
    release_phase: string;
    resolved: boolean;
    has_env_override: boolean;
    registry_default: boolean;
    description: string;
}

interface FeatureFlagProviderProps {
    children: ReactNode;
}

export function FeatureFlagProvider({ children }: Readonly<FeatureFlagProviderProps>) {
    useEffect(() => {
        let isMounted = true;

        const loadFlags = async () => {
            try {
                const response = await api.webui.get("/api/v1/config/features", {
                    credentials: "include",
                    headers: { Accept: "application/json" },
                    fullResponse: true,
                });

                if (!isMounted) return;

                if (response.ok) {
                    const featuresData: FeatureFlagInfo[] = await response.json();
                    const flags = Object.fromEntries(featuresData.map((f: FeatureFlagInfo) => [f.key, f.resolved]));
                    OpenFeature.setProvider(new SamFeatureProvider(flags));
                } else {
                    console.warn("Features endpoint unavailable, using default flag values:", response.status);
                    OpenFeature.setProvider(new SamFeatureProvider({}));
                }
            } catch (err) {
                if (!isMounted) return;
                console.warn("Failed to load feature flags, using default flag values:", err);
                OpenFeature.setProvider(new SamFeatureProvider({}));
            }
        };

        loadFlags();

        return () => {
            isMounted = false;
        };
    }, []);

    return <OpenFeatureProvider>{children}</OpenFeatureProvider>;
}
