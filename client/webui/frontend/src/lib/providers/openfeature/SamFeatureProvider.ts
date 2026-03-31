import type { JsonValue, Provider, ResolutionDetails } from "@openfeature/web-sdk";
import { StandardResolutionReasons } from "@openfeature/web-sdk";

export class SamFeatureProvider implements Provider {
    public readonly runsOn = "client" as const;
    readonly metadata = { name: "SamFeatureProvider" } as const;
    private flags: Record<string, boolean>;

    constructor(flags: Record<string, boolean>) {
        this.flags = { ...flags };
    }

    async initialize(): Promise<void> {}

    resolveBooleanEvaluation(flagKey: string, defaultValue: boolean): ResolutionDetails<boolean> {
        if (flagKey in this.flags) return { value: this.flags[flagKey], reason: StandardResolutionReasons.STATIC };
        return { value: defaultValue, reason: StandardResolutionReasons.DEFAULT };
    }

    resolveStringEvaluation(_flagKey: string, defaultValue: string): ResolutionDetails<string> {
        return { value: defaultValue, reason: StandardResolutionReasons.DEFAULT };
    }

    resolveNumberEvaluation(_flagKey: string, defaultValue: number): ResolutionDetails<number> {
        return { value: defaultValue, reason: StandardResolutionReasons.DEFAULT };
    }

    resolveObjectEvaluation<T extends JsonValue>(_flagKey: string, defaultValue: T): ResolutionDetails<T> {
        return { value: defaultValue, reason: StandardResolutionReasons.DEFAULT };
    }
}
