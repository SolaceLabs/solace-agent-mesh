/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ResearchPlanVerification, type ResearchPlanData } from "@/lib/components/research/ResearchPlanVerification";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

const basePlan: ResearchPlanData = {
    type: "deep_research_plan",
    plan_id: "plan-1",
    title: "Demo plan",
    research_question: "Why is the sky blue?",
    steps: ["Step one", "Step two"],
    research_type: "quick",
    max_iterations: 2,
    max_runtime_seconds: 60,
    sources: ["web"],
};

function renderComponent(planData: ResearchPlanData = basePlan, chatContextValues = {}) {
    return render(
        <StoryProvider chatContextValues={chatContextValues}>
            <ResearchPlanVerification planData={planData} />
        </StoryProvider>
    );
}

function makeFetchMock(response: Partial<Response> & { ok?: boolean } = { ok: true }) {
    return vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: "ok" }),
        text: () => Promise.resolve(""),
        ...response,
    });
}

describe("ResearchPlanVerification", () => {
    beforeEach(() => {
        vi.unstubAllGlobals();
    });

    test("renders plan title and steps", () => {
        renderComponent();
        expect(screen.getByText("Demo plan")).toBeInTheDocument();
        expect(screen.getByText("Step one")).toBeInTheDocument();
        expect(screen.getByText("Step two")).toBeInTheDocument();
    });

    test("renders nothing when the plan is already responded", () => {
        const { container } = renderComponent({ ...basePlan, responded: "start" });
        expect(container).toBeEmptyDOMElement();
    });

    test("clicking Start POSTs to /research/plan-response and marks the message responded", async () => {
        const fetchMock = makeFetchMock();
        vi.stubGlobal("fetch", fetchMock);
        const setMessages = vi.fn();

        renderComponent(basePlan, { setMessages });
        fireEvent.click(screen.getByRole("button", { name: /start/i }));

        await waitFor(() => expect(fetchMock).toHaveBeenCalled());
        const [url, init] = fetchMock.mock.calls[0];
        expect(String(url)).toContain("/api/v1/research/plan-response");
        const body = JSON.parse(String(init?.body ?? "{}"));
        expect(body).toMatchObject({ planId: "plan-1", action: "start", steps: basePlan.steps });
        expect(setMessages).toHaveBeenCalled();
    });

    test("clicking Cancel POSTs a cancel action", async () => {
        const fetchMock = makeFetchMock();
        vi.stubGlobal("fetch", fetchMock);

        renderComponent();
        fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

        await waitFor(() => expect(fetchMock).toHaveBeenCalled());
        const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body ?? "{}"));
        expect(body).toMatchObject({ planId: "plan-1", action: "cancel" });
        expect(body.steps).toBeUndefined();
    });

    test("surfaces a displayError when the mutation fails", async () => {
        vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
        const displayError = vi.fn();

        renderComponent(basePlan, { displayError });
        fireEvent.click(screen.getByRole("button", { name: /start/i }));

        await waitFor(() => {
            expect(displayError).toHaveBeenCalledWith(expect.objectContaining({ title: expect.any(String), error: expect.any(String) }));
        });
    });
});
