/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, beforeEach, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import type { Project } from "@/lib/types/projects";

expect.extend(matchers);

// Mock projects data with mixed pinned/unpinned states
const pinnedProject: Project = {
    id: "project-pinned",
    name: "Zebra Project",
    userId: "user-1",
    isPinned: true,
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
};

const unpinnedProjectA: Project = {
    id: "project-alpha",
    name: "Alpha Project",
    userId: "user-1",
    isPinned: false,
    createdAt: "2024-01-02T00:00:00Z",
    updatedAt: "2024-01-02T00:00:00Z",
};

const unpinnedProjectB: Project = {
    id: "project-beta",
    name: "Beta Project",
    userId: "user-1",
    isPinned: false,
    createdAt: "2024-01-03T00:00:00Z",
    updatedAt: "2024-01-03T00:00:00Z",
};

const anotherPinnedProject: Project = {
    id: "project-pinned-2",
    name: "Apple Project",
    userId: "user-1",
    isPinned: true,
    createdAt: "2024-01-04T00:00:00Z",
    updatedAt: "2024-01-04T00:00:00Z",
};

describe("ProjectProvider sort logic", () => {
    let ProjectProvider: React.ComponentType<{ children: React.ReactNode }>;
    let useProjectContext: () => { projects: Project[]; filteredProjects: Project[] };
    let mockUseProjects: ReturnType<typeof vi.fn>;

    beforeEach(async () => {
        vi.resetModules();

        mockUseProjects = vi.fn();

        vi.doMock("@/lib/api/projects/hooks", () => ({
            useProjects: mockUseProjects,
            useCreateProject: () => ({ mutateAsync: vi.fn() }),
            useUpdateProject: () => ({ mutateAsync: vi.fn() }),
            useDeleteProject: () => ({ mutateAsync: vi.fn() }),
            useAddFilesToProject: () => ({ mutateAsync: vi.fn() }),
            useRemoveFileFromProject: () => ({ mutateAsync: vi.fn() }),
            useUpdateFileMetadata: () => ({ mutateAsync: vi.fn() }),
            useFetchProjectsOnMount: () => ({ data: undefined, isLoading: false }),
        }));

        vi.doMock("@/lib/hooks", () => ({
            useConfigContext: () => ({ projectsEnabled: true }),
        }));

        const mod = await import("@/lib/providers/ProjectProvider");
        ProjectProvider = mod.ProjectProvider;
        useProjectContext = mod.useProjectContext;
    });

    function TestConsumer() {
        const { projects } = useProjectContext();
        return (
            <div>
                {projects.map((p, i) => (
                    <div key={p.id} data-testid={`project-${i}`} data-pinned={String(p.isPinned)}>
                        {p.name}
                    </div>
                ))}
            </div>
        );
    }

    test("pinned projects appear before unpinned projects", async () => {
        mockUseProjects.mockReturnValue({
            data: {
                projects: [unpinnedProjectA, pinnedProject, unpinnedProjectB],
                total: 3,
            },
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        render(
            <ProjectProvider>
                <TestConsumer />
            </ProjectProvider>
        );

        await waitFor(() => {
            expect(screen.getByTestId("project-0")).toBeInTheDocument();
        });

        // First project should be pinned
        expect(screen.getByTestId("project-0")).toHaveAttribute("data-pinned", "true");
        expect(screen.getByTestId("project-0")).toHaveTextContent("Zebra Project");

        // Remaining projects should be unpinned
        expect(screen.getByTestId("project-1")).toHaveAttribute("data-pinned", "false");
        expect(screen.getByTestId("project-2")).toHaveAttribute("data-pinned", "false");
    });

    test("unpinned projects are sorted alphabetically", async () => {
        mockUseProjects.mockReturnValue({
            data: {
                projects: [unpinnedProjectB, unpinnedProjectA],
                total: 2,
            },
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        render(
            <ProjectProvider>
                <TestConsumer />
            </ProjectProvider>
        );

        await waitFor(() => {
            expect(screen.getByTestId("project-0")).toBeInTheDocument();
        });

        // Alpha comes before Beta alphabetically
        expect(screen.getByTestId("project-0")).toHaveTextContent("Alpha Project");
        expect(screen.getByTestId("project-1")).toHaveTextContent("Beta Project");
    });

    test("multiple pinned projects are sorted alphabetically among themselves", async () => {
        mockUseProjects.mockReturnValue({
            data: {
                projects: [pinnedProject, anotherPinnedProject, unpinnedProjectA],
                total: 3,
            },
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        render(
            <ProjectProvider>
                <TestConsumer />
            </ProjectProvider>
        );

        await waitFor(() => {
            expect(screen.getByTestId("project-0")).toBeInTheDocument();
        });

        // Pinned projects first, alphabetically: Apple before Zebra
        expect(screen.getByTestId("project-0")).toHaveTextContent("Apple Project");
        expect(screen.getByTestId("project-1")).toHaveTextContent("Zebra Project");
        // Unpinned last
        expect(screen.getByTestId("project-2")).toHaveTextContent("Alpha Project");
    });

    test("returns empty array when projects feature is disabled", async () => {
        vi.resetModules();

        vi.doMock("@/lib/api/projects/hooks", () => ({
            useProjects: () => ({
                data: { projects: [unpinnedProjectA], total: 1 },
                isLoading: false,
                error: null,
                refetch: vi.fn(),
            }),
            useCreateProject: () => ({ mutateAsync: vi.fn() }),
            useUpdateProject: () => ({ mutateAsync: vi.fn() }),
            useDeleteProject: () => ({ mutateAsync: vi.fn() }),
            useAddFilesToProject: () => ({ mutateAsync: vi.fn() }),
            useRemoveFileFromProject: () => ({ mutateAsync: vi.fn() }),
            useUpdateFileMetadata: () => ({ mutateAsync: vi.fn() }),
        }));

        vi.doMock("@/lib/hooks", () => ({
            useConfigContext: () => ({ projectsEnabled: false }),
        }));

        const mod = await import("@/lib/providers/ProjectProvider");
        const DisabledProjectProvider = mod.ProjectProvider;
        const useDisabledContext = mod.useProjectContext;

        function DisabledConsumer() {
            const { projects } = useDisabledContext();
            return <div data-testid="count">{projects.length}</div>;
        }

        render(
            <DisabledProjectProvider>
                <DisabledConsumer />
            </DisabledProjectProvider>
        );

        await waitFor(() => {
            expect(screen.getByTestId("count")).toHaveTextContent("0");
        });
    });

    test("filteredProjects filters by search query", async () => {
        mockUseProjects.mockReturnValue({
            data: {
                projects: [unpinnedProjectA, unpinnedProjectB, pinnedProject],
                total: 3,
            },
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        function FilterConsumer() {
            const { filteredProjects, setSearchQuery } = useProjectContext() as ReturnType<typeof useProjectContext> & { setSearchQuery: (q: string) => void };
            React.useEffect(() => {
                setSearchQuery("alpha");
            }, [setSearchQuery]);
            return (
                <div>
                    {filteredProjects.map((p, i) => (
                        <div key={p.id} data-testid={`filtered-${i}`}>
                            {p.name}
                        </div>
                    ))}
                </div>
            );
        }

        render(
            <ProjectProvider>
                <FilterConsumer />
            </ProjectProvider>
        );

        await waitFor(() => {
            expect(screen.getByTestId("filtered-0")).toBeInTheDocument();
        });

        expect(screen.getByTestId("filtered-0")).toHaveTextContent("Alpha Project");
        expect(screen.queryByTestId("filtered-1")).toBeNull();
    });
});
