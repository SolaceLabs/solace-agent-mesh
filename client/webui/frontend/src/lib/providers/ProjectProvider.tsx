import React, { createContext, useContext, useState } from "react";

import type { Project, ProjectContextValue } from "@/lib/types/projects";

export const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [activeProject, setActiveProject] = useState<Project | null>(null);

    const value: ProjectContextValue = {
        activeProject,
        setActiveProject,
    };

    return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
};

export const useProjectContext = () => {
    const context = useContext(ProjectContext);
    if (context === undefined) {
        throw new Error("useProjectContext must be used within a ProjectProvider");
    }
    return context;
};
