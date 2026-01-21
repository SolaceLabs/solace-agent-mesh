import type { Project } from "@/lib/types/projects";

// ============================================================================
// Mock Project Data
// ============================================================================

export const weatherProject: Project = {
    id: "project-1",
    name: "Weather App",
    userId: "user-id",
    description: "A project for weather forecasting features",
    systemPrompt: "You are a helpful assistant for weather-related tasks.",
    defaultAgentId: "OrchestratorAgent",
    artifactCount: 5,
    createdAt: new Date("2024-01-10").toISOString(),
    updatedAt: new Date("2024-02-15").toISOString(),
};

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

export const populatedProject: Project = {
    id: "project-populated",
    name: "AI Chat Assistant",
    userId: "user-id",
    description: "A comprehensive AI-powered chat assistant with advanced features and knowledge base integration.",
    systemPrompt: "You are a helpful AI assistant specialized in software development. Provide clear, concise answers with code examples when appropriate. Always explain your reasoning and suggest best practices.",
    defaultAgentId: "OrchestratorAgent",
    artifactCount: 15,
    createdAt: new Date("2024-01-15").toISOString(),
    updatedAt: new Date("2024-03-20").toISOString(),
};

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

export const projectWithLongDescription: Project = {
    id: "project-long-desc",
    name: "Documentation System",
    userId: "user-id",
    description:
        "This is a comprehensive documentation management system designed to help teams collaborate on technical documentation, API references, user guides, and internal knowledge bases. It includes features like version control, collaborative editing, markdown support, and automated publishing workflows.",
    systemPrompt: null,
    defaultAgentId: null,
    artifactCount: 8,
    createdAt: new Date("2024-02-01").toISOString(),
    updatedAt: new Date("2024-02-28").toISOString(),
};

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

export const allProjects: Project[] = [weatherProject, eCommerceProject, populatedProject, emptyProject, projectWithLongDescription, projectWithManyArtifacts];
