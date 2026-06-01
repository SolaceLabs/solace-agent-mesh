import { describe, test, expect } from "vitest";
import { selectInitialAgent } from "@/lib/utils/agentUtils";
import type { AgentCardInfo } from "@/lib/types";

const agent = (name: string): AgentCardInfo => ({ name, displayName: name }) as unknown as AgentCardInfo;

const orchestrator = agent("OrchestratorAgent");
const alpha = agent("AlphaAgent");
const beta = agent("BetaAgent");

describe("selectInitialAgent — pinned agent (embedded mode)", () => {
    test("selects the URL agent and never seeds the welcome bubble", () => {
        const result = selectInitialAgent({ agents: [orchestrator, alpha], urlAgentName: "AlphaAgent", embedded: true });

        expect(result.agent).toBe(alpha);
        expect(result.shouldSeedWelcome).toBe(false);
    });

    test("bails when the pinned agent is not yet available", () => {
        const result = selectInitialAgent({ agents: [orchestrator], urlAgentName: "AlphaAgent", embedded: true });

        expect(result.agent).toBeNull();
        expect(result.shouldSeedWelcome).toBe(false);
    });

    test("bails when no ?agent= is given — embedded never falls back to a default", () => {
        // Even with an OrchestratorAgent available, a missing ?agent= must not silently
        // pin to it; the embedded surface requires an explicit agent (caller shows an error).
        const result = selectInitialAgent({ agents: [alpha, orchestrator], urlAgentName: null, embedded: true });

        expect(result.agent).toBeNull();
        expect(result.shouldSeedWelcome).toBe(false);
    });

    test("ignores the project default — embedded only honors an explicit ?agent=", () => {
        const result = selectInitialAgent({ agents: [alpha, beta], urlAgentName: null, embedded: true, projectDefaultAgentId: "BetaAgent" });

        expect(result.agent).toBeNull();
        expect(result.shouldSeedWelcome).toBe(false);
    });

    test("pins by wire name only — a shared displayName cannot misroute", () => {
        // Two agents collide on displayName but have distinct wire names. ?agent=
        // must resolve against the unique wire name, never the ambiguous label.
        const first = { name: "agent-uuid-1", displayName: "Weather Agent" } as unknown as AgentCardInfo;
        const second = { name: "agent-uuid-2", displayName: "Weather Agent" } as unknown as AgentCardInfo;
        const result = selectInitialAgent({ agents: [first, second], urlAgentName: "agent-uuid-2", embedded: true });

        expect(result.agent).toBe(second);
    });

    test("does not resolve a ?agent= that matches only a displayName", () => {
        const platform = { name: "agent-uuid-1", displayName: "Weather Agent" } as unknown as AgentCardInfo;
        const result = selectInitialAgent({ agents: [platform], urlAgentName: "Weather Agent", embedded: true });

        expect(result.agent).toBeNull();
    });
});

describe("selectInitialAgent — priority order (full UI)", () => {
    test("URL agent wins and the welcome bubble is seeded", () => {
        const result = selectInitialAgent({ agents: [orchestrator, alpha], urlAgentName: "AlphaAgent", embedded: false });

        expect(result.agent).toBe(alpha);
        expect(result.shouldSeedWelcome).toBe(true);
    });

    test("falls back to priority order when the URL agent is unknown", () => {
        const result = selectInitialAgent({ agents: [alpha, orchestrator], urlAgentName: "GhostAgent", embedded: false });

        expect(result.agent).toBe(orchestrator);
        expect(result.shouldSeedWelcome).toBe(true);
    });

    test("uses the project default agent when present", () => {
        const result = selectInitialAgent({ agents: [orchestrator, alpha, beta], urlAgentName: null, embedded: false, projectDefaultAgentId: "BetaAgent" });

        expect(result.agent).toBe(beta);
    });

    test("falls back to OrchestratorAgent when the project default is missing", () => {
        const result = selectInitialAgent({ agents: [alpha, orchestrator], urlAgentName: null, embedded: false, projectDefaultAgentId: "GhostAgent" });

        expect(result.agent).toBe(orchestrator);
    });

    test("prefers OrchestratorAgent over the first agent when no project default", () => {
        const result = selectInitialAgent({ agents: [alpha, orchestrator], urlAgentName: null, embedded: false });

        expect(result.agent).toBe(orchestrator);
    });

    test("falls back to the first agent when OrchestratorAgent is absent", () => {
        const result = selectInitialAgent({ agents: [alpha, beta], urlAgentName: null, embedded: false });

        expect(result.agent).toBe(alpha);
    });
});
