/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect, vi } from "vitest";
import meta from "./ProjectCard.stories";
import * as matchers from "@testing-library/jest-dom/matchers";
import type { Project } from "@/lib/types/projects";
import { ownerWithProjectSharingEnabled, viewerWithProjectSharingEnabled, ownerWithAuthorization } from "@/stories/data/parameters";

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
                    parameters: ownerWithProjectSharingEnabled("owner-user"),
                },
                meta
            );

            render(<OwnerWithSharing />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();

            const ownerIcon = document.querySelector(".lucide-user");
            expect(ownerIcon).toBeInTheDocument();

            const viewerIcon = document.querySelector(".lucide-eye");
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
                    parameters: viewerWithProjectSharingEnabled(),
                },
                meta
            );

            render(<ViewerWithSharing />);

            expect(await screen.findByText(mockProject.name)).toBeInTheDocument();

            const viewerIcon = document.querySelector(".lucide-eye");
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
                    parameters: ownerWithProjectSharingEnabled("owner-user"),
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
                    parameters: viewerWithProjectSharingEnabled(),
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
                    parameters: ownerWithAuthorization("owner-user"),
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
                    parameters: viewerWithProjectSharingEnabled(),
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
                    parameters: ownerWithAuthorization("owner-user"),
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
                    parameters: ownerWithAuthorization("owner-user"),
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

        describe("Pin/Star Button", () => {
            test("pin button shown when onTogglePin is provided", async () => {
                const OwnerWithPin = composeStory(
                    {
                        args: {
                            project: mockProject,
                            onDelete: () => {},
                            onTogglePin: () => {},
                        },
                        parameters: ownerWithAuthorization("owner-user"),
                    },
                    meta
                );

                render(<OwnerWithPin />);

                expect(await screen.findByText(mockProject.name)).toBeInTheDocument();
                expect(screen.getByRole("button", { name: "Add to favorites" })).toBeInTheDocument();
            });

            test("pin button NOT shown when onTogglePin is not provided", async () => {
                const OwnerWithoutPin = composeStory(
                    {
                        args: {
                            project: mockProject,
                            onDelete: () => {},
                        },
                        parameters: ownerWithAuthorization("owner-user"),
                    },
                    meta
                );

                render(<OwnerWithoutPin />);

                expect(await screen.findByText(mockProject.name)).toBeInTheDocument();
                expect(screen.queryByRole("button", { name: "Add to favorites" })).toBeNull();
                expect(screen.queryByRole("button", { name: "Remove from favorites" })).toBeNull();
            });

            test("pin button shows filled star when project is pinned", async () => {
                const pinnedProject = { ...mockProject, isPinned: true };
                const PinnedCard = composeStory(
                    {
                        args: {
                            project: pinnedProject,
                            onDelete: () => {},
                            onTogglePin: () => {},
                        },
                        parameters: ownerWithAuthorization("owner-user"),
                    },
                    meta
                );

                render(<PinnedCard />);

                expect(await screen.findByText(mockProject.name)).toBeInTheDocument();
                expect(screen.getByRole("button", { name: "Remove from favorites" })).toBeInTheDocument();
            });

            test("onTogglePin callback triggered with project when clicking pin button", async () => {
                const user = userEvent.setup();
                const mockOnTogglePin = vi.fn();

                const CardWithPin = composeStory(
                    {
                        args: {
                            project: mockProject,
                            onDelete: () => {},
                            onTogglePin: mockOnTogglePin,
                        },
                        parameters: ownerWithAuthorization("owner-user"),
                    },
                    meta
                );

                render(<CardWithPin />);

                const pinButton = await screen.findByRole("button", { name: "Add to favorites" });
                await user.click(pinButton);

                await waitFor(() => {
                    expect(mockOnTogglePin).toHaveBeenCalledTimes(1);
                });

                expect(mockOnTogglePin).toHaveBeenCalledWith(mockProject);
            });

            test("pin button click does not trigger card onClick", async () => {
                const user = userEvent.setup();
                const mockOnClick = vi.fn();
                const mockOnTogglePin = vi.fn();

                const CardWithPin = composeStory(
                    {
                        args: {
                            project: mockProject,
                            onClick: mockOnClick,
                            onDelete: () => {},
                            onTogglePin: mockOnTogglePin,
                        },
                        parameters: ownerWithAuthorization("owner-user"),
                    },
                    meta
                );

                render(<CardWithPin />);

                const pinButton = await screen.findByRole("button", { name: "Add to favorites" });
                await user.click(pinButton);

                await waitFor(() => {
                    expect(mockOnTogglePin).toHaveBeenCalledTimes(1);
                });

                expect(mockOnClick).not.toHaveBeenCalled();
            });

            test("pin button is disabled when isPinToggling is true", async () => {
                const CardWithPinToggling = composeStory(
                    {
                        args: {
                            project: mockProject,
                            onDelete: () => {},
                            onTogglePin: () => {},
                            isPinToggling: true,
                        },
                        parameters: ownerWithAuthorization("owner-user"),
                    },
                    meta
                );

                render(<CardWithPinToggling />);

                const pinButton = await screen.findByRole("button", { name: "Add to favorites" });
                expect(pinButton).toBeDisabled();
            });
        });
    });
});
