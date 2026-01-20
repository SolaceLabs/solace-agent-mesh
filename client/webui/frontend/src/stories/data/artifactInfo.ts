import type { ArtifactInfo } from "@/lib/types";

// ============================================================================
// Mock ArtifactInfo Data
// ============================================================================

export const pdfArtifact: ArtifactInfo = {
    filename: "api-documentation.pdf",
    mime_type: "application/pdf",
    size: 524288,
    last_modified: new Date("2024-03-15T10:00:00Z").toISOString(),
    description: "API reference documentation",
};

export const imageArtifact: ArtifactInfo = {
    filename: "architecture-diagram.png",
    mime_type: "image/png",
    size: 204800,
    last_modified: new Date("2024-03-18T14:30:00Z").toISOString(),
    description: "System architecture overview",
};

export const jsonArtifact: ArtifactInfo = {
    filename: "package.json",
    mime_type: "application/json",
    size: 1024,
    last_modified: new Date("2024-03-17T09:45:00Z").toISOString(),
    description: "",
};

export const markdownArtifact: ArtifactInfo = {
    filename: "README.md",
    mime_type: "text/markdown",
    size: 4096,
    last_modified: new Date("2024-03-16T12:20:00Z").toISOString(),
    description: "Project overview and setup instructions",
};

export const artifactWithLongDescription: ArtifactInfo = {
    filename: "design-spec.pdf",
    mime_type: "application/pdf",
    size: 1048576,
    last_modified: new Date("2024-03-20T11:00:00Z").toISOString(),
    description: "API reference documentation for the project endpoints including authentication, data models, and error handling patterns",
};
