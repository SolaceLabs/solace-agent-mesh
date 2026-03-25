import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
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
    const { data, isError } = useQuery<FeatureFlagInfo[]>({
        queryKey: ["config", "features"],
        queryFn: async () => {
            const response = await api.webui.get("/api/v1/config/features", {
                credentials: "include",
                headers: { Accept: "application/json" },
                fullResponse: true,
            });
            if (!response.ok) {
                throw new Error(`Features endpoint returned ${response.status}`);
            }
            return response.json();
        },
        retry: 0,
        staleTime: Infinity,
    });

    useEffect(() => {
        if (data) {
            const flags = Object.fromEntries(data.map(f => [f.key, f.resolved]));
            OpenFeature.setProvider(new SamFeatureProvider(flags));
        } else if (isError) {
            console.warn("Failed to load feature flags, using default flag values");
            OpenFeature.setProvider(new SamFeatureProvider({}));
        }
    }, [data, isError]);

    return <OpenFeatureProvider>{children}</OpenFeatureProvider>;
}
