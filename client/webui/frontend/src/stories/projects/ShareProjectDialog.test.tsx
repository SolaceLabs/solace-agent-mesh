/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import meta from "./ShareProjectDialog.stories";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

const mockSharesResponse = {
    projectId: "project-1",
    ownerEmail: "owner@example.com",
    shares: [
        {
            id: "share-1",
            projectId: "project-1",
            userEmail: "viewer1@example.com",
            accessLevel: "RESOURCE_VIEWER",
            sharedByEmail: "owner@example.com",
            createdAt: "2024-01-01T00:00:00Z",
            updatedAt: "2024-01-01T00:00:00Z",
        },
    ],
};

const server = setupServer(
    http.get("*/api/v1/config", () => {
        return HttpResponse.json({});
    }),
    http.get("*/api/v1/speech/config", () => {
        return HttpResponse.json({});
    }),
    http.get("*/api/v1/projects/*/shares", () => {
        return HttpResponse.json(mockSharesResponse);
    })
);

const mockProject = {
    id: "project-1",
    name: "Test Project",
    userId: "user-1",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
};

const WithoutIdentityService = composeStory(
    {
        args: {
            isOpen: true,
            onClose: () => {},
            project: mockProject,
        },
        parameters: {
            configContext: {
                identityServiceType: null,
            },
        },
    },
    meta
);

const WithExistingShares = composeStory(
    {
        args: {
            isOpen: true,
            onClose: () => {},
            project: mockProject,
        },
    },
    meta
);

describe("ShareProjectDialog", () => {
    beforeAll(() => server.listen());
    afterEach(() => server.resetHandlers());
    afterAll(() => server.close());

    describe("WithoutIdentityService", () => {
        test("validates email format", async () => {
            const user = userEvent.setup();
            render(<WithoutIdentityService />);

            expect(await screen.findByRole("dialog")).toBeInTheDocument();

            const addButton = await screen.findByRole("button", { name: /Add/ });
            await user.click(addButton);

            const emailInput = await screen.findByPlaceholderText("Enter email address...");
            await user.type(emailInput, "invalid-email");

            const saveButton = await screen.findByRole("button", { name: /Save/ });
            await user.click(saveButton);

            await waitFor(() => {
                expect(screen.getByText("Please enter a valid email address")).toBeInTheDocument();
            });
        });

        test("submits create shares API with correct payload", async () => {
            const user = userEvent.setup();
            let capturedRequestBody: unknown = null;

            server.use(
                http.post("*/api/v1/projects/*/shares", async ({ request }) => {
                    capturedRequestBody = await request.json();
                    return HttpResponse.json(
                        {
                            projectId: "project-1",
                            created: [
                                {
                                    id: "new-share",
                                    projectId: "project-1",
                                    userEmail: "test@example.com",
                                    accessLevel: "RESOURCE_VIEWER",
                                    sharedByEmail: "owner@example.com",
                                    createdAt: "2024-01-01T00:00:00Z",
                                    updatedAt: "2024-01-01T00:00:00Z",
                                },
                            ],
                            updated: [],
                            totalProcessed: 1,
                        },
                        { status: 201 }
                    );
                })
            );

            render(<WithoutIdentityService />);

            expect(await screen.findByRole("dialog")).toBeInTheDocument();

            const addButton = await screen.findByRole("button", { name: /Add/ });
            await user.click(addButton);

            const emailInput = await screen.findByPlaceholderText("Enter email address...");
            await user.type(emailInput, "test@example.com");

            const saveButton = await screen.findByRole("button", { name: /Save/ });
            await user.click(saveButton);

            await waitFor(() => {
                expect(capturedRequestBody).not.toBeNull();
            });

            expect(capturedRequestBody).toMatchObject({
                shares: [{ userEmail: "test@example.com", accessLevel: "RESOURCE_VIEWER" }],
            });
        });
    });

    describe("WithExistingShares", () => {
        test("submits delete shares API when removing existing viewer", async () => {
            const user = userEvent.setup();
            let capturedDeleteBody: unknown = null;

            server.use(
                http.delete("*/api/v1/projects/*/shares", async ({ request }) => {
                    capturedDeleteBody = await request.json();
                    return HttpResponse.json({
                        projectId: "project-1",
                        deletedCount: 1,
                        deletedEmails: ["viewer1@example.com"],
                    });
                })
            );

            render(<WithExistingShares />);

            expect(await screen.findByRole("dialog")).toBeInTheDocument();
            expect(await screen.findByText("viewer1@example.com")).toBeInTheDocument();

            const viewerRow = screen.getByText("viewer1@example.com").closest("div");
            const removeButtons = viewerRow?.parentElement?.querySelectorAll("button");
            const removeButton = removeButtons ? Array.from(removeButtons).find(btn => btn.querySelector("svg")) : null;

            if (removeButton) {
                await user.click(removeButton);
            }

            const saveButton = await screen.findByRole("button", { name: /Save/ });
            await user.click(saveButton);

            await waitFor(() => {
                expect(capturedDeleteBody).not.toBeNull();
            });

            expect(capturedDeleteBody).toMatchObject({
                userEmails: ["viewer1@example.com"],
            });
        });
    });
});
