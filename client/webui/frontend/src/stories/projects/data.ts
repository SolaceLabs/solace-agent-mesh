import type { Project } from "@/lib/types/projects";

// ============================================================================
// Individual Project Fixtures
// ============================================================================

/**
 * A basic project with minimal configuration.
 * Use for: Testing basic project display and interactions.
 */
export const weatherProject: Project = {
    id: "project-1",
    name: "Weather App",
    userId: "user-id",
    description: "A project for weather forecasting features",
    systemPrompt: "You are a helpful assistant for weather-related tasks.",
    defaultAgentId: "agent-1",
    artifactCount: 5,
    createdAt: new Date("2024-01-10").toISOString(),
    updatedAt: new Date("2024-02-15").toISOString(),
};

/**
 * A project with null values for optional fields.
 * Use for: Testing how the UI handles missing data.
 */
export const eCommerceProject: Project = {
    id: "project-2",
    name: "E-commerce Platform",
    userId: "user-id",
    description: "Online shopping platform development",
    systemPrompt: null,
    defaultAgentId: null,
    artifactCount: 12,
    createdAt: new Date("2023-12-05").toISOString(),
    updatedAt: new Date("2024-03-01").toISOString(),
};

/**
 * A fully populated project with all fields set.
 * Use for: ProjectDetailView stories showing complete project data.
 */
export const populatedProject: Project = {
    id: "project-populated",
    name: "AI Chat Assistant",
    userId: "user-id",
    description: "A comprehensive AI-powered chat assistant with advanced features and knowledge base integration.",
    systemPrompt: "You are a helpful AI assistant specialized in software development. Provide clear, concise answers with code examples when appropriate. Always explain your reasoning and suggest best practices.",
    defaultAgentId: "agent-1",
    artifactCount: 15,
    createdAt: new Date("2024-01-15").toISOString(),
    updatedAt: new Date("2024-03-20").toISOString(),
};

/**
 * A newly created empty project.
 * Use for: ProjectDetailView stories showing empty state for new projects.
 */
export const emptyProject: Project = {
    id: "project-empty",
    name: "New Project",
    userId: "user-id",
    description: "",
    systemPrompt: null,
    defaultAgentId: null,
    artifactCount: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
};

/**
 * A project with a very long description.
 * Use for: Testing text truncation and overflow handling.
 */
export const projectWithLongDescription: Project = {
    id: "project-long-desc",
    name: "Documentation System",
    userId: "user-id",
    description: "This is a comprehensive documentation management system designed to help teams collaborate on technical documentation, API references, user guides, and internal knowledge bases. It includes features like version control, collaborative editing, markdown support, and automated publishing workflows.",
    systemPrompt: null,
    defaultAgentId: null,
    artifactCount: 8,
    createdAt: new Date("2024-02-01").toISOString(),
    updatedAt: new Date("2024-02-28").toISOString(),
};

/**
 * A project with many artifacts.
 * Use for: Testing high artifact count display.
 */
export const projectWithManyArtifacts: Project = {
    id: "project-many-artifacts",
    name: "Data Analysis Pipeline",
    userId: "user-id",
    description: "Large-scale data processing and analysis project",
    systemPrompt: null,
    defaultAgentId: "agent-2",
    artifactCount: 157,
    createdAt: new Date("2023-11-20").toISOString(),
    updatedAt: new Date("2024-03-15").toISOString(),
};

// ============================================================================
// Project Collections
// ============================================================================

/**
 * Default set of projects for general testing.
 * Use for: ProjectsPage default story and general project list testing.
 */
export const defaultProjects: Project[] = [weatherProject, eCommerceProject];

/**
 * All available project fixtures.
 * Use for: Testing with a larger variety of projects.
 */
export const allProjects: Project[] = [
    weatherProject,
    eCommerceProject,
    populatedProject,
    emptyProject,
    projectWithLongDescription,
    projectWithManyArtifacts,
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Creates a mock project with customizable properties.
 * Use for: Generating projects dynamically in tests.
 *
 * @param overrides - Partial project properties to override defaults
 * @returns A complete Project object
 */
export const createMockProject = (overrides: Partial<Project> = {}): Project => {
    const baseProject: Project = {
        id: `project-${Date.now()}`,
        name: "Mock Project",
        userId: "user-id",
        description: "A mock project for testing",
        systemPrompt: null,
        defaultAgentId: null,
        artifactCount: 0,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
    };

    return { ...baseProject, ...overrides };
};

/**
 * Generates multiple mock projects for bulk testing.
 * Use for: Performance testing and pagination scenarios.
 *
 * @param count - Number of projects to generate
 * @returns Array of mock projects
 */
export const generateMockProjects = (count: number): Project[] => {
    return Array.from({ length: count }, (_, index) =>
        createMockProject({
            id: `project-${index}`,
            name: `Project ${index + 1}`,
            description: `Description for project ${index + 1}`,
            artifactCount: Math.floor(Math.random() * 20),
        })
    );
};