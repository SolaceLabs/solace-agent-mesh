/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { composeStory } from "@storybook/react";
import { describe, test, expect, vi } from "vitest";
import meta from "./ProjectDetailView.stories";
import * as matchers from "@testing-library/jest-dom/matchers";
import { populatedProject } from "../data/projects";

expect.extend(matchers);

describe("ProjectDetailView", () => {
    describe("Button Visibility for Viewers", () => {
        test("viewer cannot see edit buttons when not owner", async () => {
            const ViewerStory = composeStory(
                {
                    args: {
                        project: populatedProject,
                        onBack: () => {},
                        onStartNewChat: () => {},
                        onChatClick: () => {},
                        onShare: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "different-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                        },
                    },
                },
                meta
            );

            render(<ViewerStory />);

            expect(await screen.findByText(populatedProject.description!)).toBeInTheDocument();

            expect(screen.queryByTestId("editDetailsButton")).not.toBeInTheDocument();

            expect(screen.queryByTestId("shareButton")).not.toBeInTheDocument();

            const moreOptionsButton = document.querySelector(".lucide-more-horizontal");
            expect(moreOptionsButton).not.toBeInTheDocument();
        });
    });

    describe("Share Button Visibility for Owners", () => {
        test("owner with sharing enabled sees Share button", async () => {
            const mockOnShare = vi.fn();

            const OwnerWithSharingStory = composeStory(
                {
                    args: {
                        project: populatedProject,
                        onBack: () => {},
                        onStartNewChat: () => {},
                        onChatClick: () => {},
                        onShare: mockOnShare,
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "user-id" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                        },
                    },
                },
                meta
            );

            render(<OwnerWithSharingStory />);

            expect(await screen.findByText(populatedProject.description!)).toBeInTheDocument();

            const shareButton = await screen.findByTestId("shareButton");
            expect(shareButton).toBeInTheDocument();
            expect(shareButton).toBeVisible();
        });
    });
});
