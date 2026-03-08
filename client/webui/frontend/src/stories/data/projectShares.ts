import type { Project, ProjectSharesResponse } from "@/lib/types/projects";

// ============================================================================
// Mock Project Data for Sharing Stories
// ============================================================================

export const mockProject: Project = {
    id: "project-1",
    name: "Test Project",
    userId: "user-1",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
};

export const mockEmptyProject: Project = {
    id: "project-empty",
    name: "Empty Project",
    userId: "user-1",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
};

// ============================================================================
// Mock Shares Response Data
// ============================================================================

export const mockSharesResponse: ProjectSharesResponse = {
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

export const mockEmptySharesResponse: ProjectSharesResponse = {
    projectId: "project-empty",
    ownerEmail: "owner@example.com",
    shares: [],
};

// ============================================================================
// Mock People Search Response
// ============================================================================

export const mockPeopleSearchResponse = {
    data: [
        { id: "person-1", workEmail: "alice@example.com" },
        { id: "person-2", workEmail: "bob@example.com" },
        { id: "person-3", workEmail: "charlie@example.com" },
    ],
};
