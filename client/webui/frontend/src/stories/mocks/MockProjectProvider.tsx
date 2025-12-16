import { ProjectContext } from "@/lib";
import type { Project, ProjectContextValue } from "@/lib/types/projects";

interface MockProjectProviderProps {
    children: React.ReactNode;
    mockValues: Partial<ProjectContextValue>;
}

const defaultProjectValues: ProjectContextValue = {
    isLoading: false,
    projects: [],
    error: null,
    createProject: async () => ({}) as Project,
    refetch: async () => {},
    currentProject: null,
    setCurrentProject: () => {},
    selectedProject: null,
    setSelectedProject: () => {},
    activeProject: null,
    setActiveProject: () => {},
    addFilesToProject: async () => {},
    updateProject: async () => ({}) as Project,
    removeFileFromProject: async () => {},
    updateFileMetadata: async () => {},
    deleteProject: async () => {},
    searchQuery: "",
    setSearchQuery: () => {},
    filteredProjects: [],
};

export const MockProjectProvider: React.FC<MockProjectProviderProps> = ({ children, mockValues = {} }) => {
    const contextValue = {
        ...defaultProjectValues,
        ...mockValues,
    };

    return <ProjectContext.Provider value={contextValue}>{children}</ProjectContext.Provider>;
};
