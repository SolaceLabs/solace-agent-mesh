/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect, vi } from "vitest";
import meta from "./ProjectCard.stories";
import * as matchers from "@testing-library/jest-dom/matchers";
import type { Project } from "@/lib/types/projects";

expect.extend(matchers);

const mockProject: Project = {
    id: "project-1",
    name: "Test Project",
    userId: "owner-user",
    description: "A test project",
    artifactCount: 5,
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
};

describe("ProjectCard", () => {
    describe("Ownership Icons", () => {
        test("shows UserCog icon for owner when sharing enabled", async () => {
            const OwnerWithSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                        onShare: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "owner-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                            configFeatureEnablement: {
                                projectSharingEnabled: true,
                            },
                        },
                    },
                },
                meta
            );

            render(<OwnerWithSharing />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();

            const ownerIcon = document.querySelector(".lucide-user");
            expect(ownerIcon).toBeInTheDocument();

            const viewerIcon = document.querySelector(".lucide-user-search");
            expect(viewerIcon).not.toBeInTheDocument();
        });

        test("shows UserSearch icon for viewer when sharing enabled", async () => {
            const ViewerWithSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                        onShare: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "different-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                            configFeatureEnablement: {
                                projectSharingEnabled: true,
                            },
                        },
                    },
                },
                meta
            );

            render(<ViewerWithSharing />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();

            const viewerIcon = document.querySelector(".lucide-user-search");
            expect(viewerIcon).toBeInTheDocument();

            const ownerIcon = document.querySelector(".lucide-user-cog");
            expect(ownerIcon).not.toBeInTheDocument();
        });

        test("no ownership icon shown when onShare is not provided", async () => {
            const OwnerWithoutSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "owner-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                            configFeatureEnablement: {
                                projectSharingEnabled: true,
                            },
                        },
                    },
                },
                meta
            );

            render(<OwnerWithoutSharing />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();

            expect(screen.queryByText("You are the owner of this project")).toBeNull();
            expect(screen.queryByText("You are a viewer of this project")).toBeNull();
        });
    });

    describe("Menu Visibility", () => {
        test("menu not shown for non-owner (ownership-based visibility)", async () => {
            const AsViewer = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "different-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                            configFeatureEnablement: {
                                projectSharingEnabled: true,
                            },
                        },
                    },
                },
                meta
            );

            render(<AsViewer />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();
            expect(await screen.findByText(mockProject.description!)).toBeInTheDocument();
            expect(screen.queryByRole("button", { name: "More options" })).toBeNull();
        });
    });

    describe("Share Menu Item", () => {
        test("'Share Project' menu item appears for owner when sharing enabled", async () => {
            const user = userEvent.setup();
            const mockOnShare = vi.fn();

            const OwnerWithSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                        onShare: mockOnShare,
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "owner-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                        },
                    },
                },
                meta
            );

            render(<OwnerWithSharing />);

            const menuButton = await screen.findByRole("button", { name: "More options" });
            await user.click(menuButton);

            expect(await screen.findByText("Share Project")).toBeInTheDocument();
        });

        test("'Share Project' NOT shown for non-owner (menu itself hidden)", async () => {
            const ViewerWithSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                        onShare: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "different-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                            configFeatureEnablement: {
                                projectSharingEnabled: true,
                            },
                        },
                    },
                },
                meta
            );

            render(<ViewerWithSharing />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();

            expect(screen.queryByRole("button", { name: "More options" })).toBeNull();
            expect(screen.queryByText("Share Project")).toBeNull();
        });

        test("'Share Project' NOT shown when onShare is not provided (even for owner)", async () => {
            const user = userEvent.setup();

            const OwnerWithoutSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "owner-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                        },
                    },
                },
                meta
            );

            render(<OwnerWithoutSharing />);

            const menuButton = await screen.findByRole("button", { name: "More options" });
            await user.click(menuButton);

            await waitFor(() => {
                expect(screen.getByText("Delete")).toBeInTheDocument();
            });

            expect(screen.queryByText("Share Project")).toBeNull();
        });

        test("onShare callback triggered with project when clicking 'Share Project'", async () => {
            const user = userEvent.setup();
            const mockOnShare = vi.fn();

            const OwnerWithSharing = composeStory(
                {
                    args: {
                        project: mockProject,
                        onDelete: () => {},
                        onShare: mockOnShare,
                    },
                    parameters: {
                        authContext: {
                            userInfo: { username: "owner-user" },
                        },
                        configContext: {
                            configUseAuthorization: true,
                        },
                    },
                },
                meta
            );

            render(<OwnerWithSharing />);

            const menuButton = await screen.findByRole("button", { name: "More options" });
            await user.click(menuButton);

            const shareMenuItem = await screen.findByText("Share Project");
            await user.click(shareMenuItem);

            await waitFor(() => {
                expect(mockOnShare).toHaveBeenCalledTimes(1);
            });

            expect(mockOnShare).toHaveBeenCalledWith(mockProject);
        });
    });
});
