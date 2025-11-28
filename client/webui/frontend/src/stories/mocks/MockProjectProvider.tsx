import { ProjectContext } from "@/lib";
import type { ProjectContextValue } from "@/lib/types/projects";

interface MockProjectProviderProps {
    children: React.ReactNode;
    mockValues: Partial<ProjectContextValue>;
}

const defaultProjectValues: ProjectContextValue = {
    activeProject: null,
    setActiveProject: () => {},
};

export const MockProjectProvider: React.FC<MockProjectProviderProps> = ({ children, mockValues = {} }) => {
    const contextValue = {
        ...defaultProjectValues,
        ...mockValues,
    };

    return <ProjectContext.Provider value={contextValue}>{children}</ProjectContext.Provider>;
};
