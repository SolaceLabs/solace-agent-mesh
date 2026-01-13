import type { Project } from "@/lib/types/projects";

/**
 * Checks if the user can share the project.
 * Only the project owner can share the project.
 */
export const canShareProject = (project: Project): boolean => {
    // If no role is specified, assume owner (backward compatibility)
    return project.role === "owner" || !project.role;
};

/**
 * Checks if the user can edit the project content.
 * Owners and editors can edit project content.
 */
export const canEditProject = (project: Project): boolean => {
    // If no role is specified, assume owner (backward compatibility)
    const role = project.role || "owner";
    return ["owner", "editor"].includes(role);
};

/**
 * Checks if the user can delete the project.
 * Only the project owner can delete the project.
 */
export const canDeleteProject = (project: Project): boolean => {
    // If no role is specified, assume owner (backward compatibility)
    return project.role === "owner" || !project.role;
};
