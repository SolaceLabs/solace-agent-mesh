import React, { useState } from "react";
import { Plus } from "lucide-react";

import { CreateProjectWizard } from "./CreateProjectWizard";
import { ProjectListSidebar } from "./ProjectListSidebar";
import { ProjectDetailPanel } from "./ProjectDetailPanel";
import { ProjectMetadataSidebar } from "./ProjectMetadataSidebar";
import { useProjectContext } from "@/lib/providers";
import { useChatContext } from "@/lib/hooks";
import type { Project, ProjectFormData } from "@/lib/types/projects";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { Header } from "@/lib/components/header";
import { Button } from "@/lib/components/ui";

interface ProjectsPageProps {
    onProjectActivated: () => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onProjectActivated }) => {
    const [showCreateWizard, setShowCreateWizard] = useState(false);
    const { 
        projects, 
        isLoading, 
        error, 
        createProject, 
        selectedProject, 
        setSelectedProject,
        setActiveProject,
    } = useProjectContext();
    const { handleSwitchSession } = useChatContext();

    const handleCreateProject = async (data: ProjectFormData) => {
        const formData = new FormData();
        formData.append("name", data.name);
        if (data.description) {
            formData.append("description", data.description);
        }
        if (data.system_prompt) {
            formData.append("systemPrompt", data.system_prompt);
        }
        if (data.files) {
            for (let i = 0; i < data.files.length; i++) {
                formData.append("files", data.files[i]);
            }
        }
        if (data.fileDescriptions && data.files) {
            const metadataPayload: Record<string, string> = {};
            for (const file of Array.from(data.files)) {
                if (data.fileDescriptions[file.name]) {
                    metadataPayload[file.name] = data.fileDescriptions[file.name];
                }
            }
            if (Object.keys(metadataPayload).length > 0) {
                formData.append("fileMetadata", JSON.stringify(metadataPayload));
            }
        }

        const newProject = await createProject(formData);
        setShowCreateWizard(false);
        // Auto-select the newly created project
        setSelectedProject(newProject);
    };

    const handleProjectSelect = (project: Project) => {
        setSelectedProject(project);
    };

    const handleCreateNew = () => {
        setShowCreateWizard(true);
    };

    const handleChatClick = async (sessionId: string) => {
        // Activate the project and switch to the chat
        if (selectedProject) {
            setActiveProject(selectedProject);
            await handleSwitchSession(sessionId);
            onProjectActivated();
        }
    };

    // Show wizard as overlay
    if (showCreateWizard) {
        return (
            <CreateProjectWizard
                onComplete={() => setShowCreateWizard(false)}
                onCancel={() => setShowCreateWizard(false)}
                onSubmit={handleCreateProject}
            />
        );
    }

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title={selectedProject ? selectedProject.name : "Projects"}
                breadcrumbs={selectedProject ? [
                    { label: "Projects", onClick: () => setSelectedProject(null) },
                    { label: selectedProject.name }
                ] : undefined}
                buttons={[
                    <Button key="create-project" onClick={handleCreateNew} className="flex items-center gap-2">
                        <Plus className="h-4 w-4" />
                        Create Project
                    </Button>
                ]}
            />
            <div className="flex-1 min-h-0">
                <ResizablePanelGroup direction="horizontal" className="h-full">
                    {/* Left Sidebar - Project List */}
                    <ResizablePanel
                        defaultSize={20}
                        minSize={15}
                        maxSize={30}
                        className="min-w-[200px]"
                    >
                        <ProjectListSidebar
                            projects={projects}
                            selectedProject={selectedProject}
                            isLoading={isLoading}
                            error={error}
                            onProjectSelect={handleProjectSelect}
                            onCreateNew={handleCreateNew}
                        />
                    </ResizablePanel>

                    <ResizableHandle />

                    {/* Center Panel - Project Details */}
                    <ResizablePanel defaultSize={55} minSize={40}>
                        <ProjectDetailPanel
                            selectedProject={selectedProject}
                            onCreateNew={handleCreateNew}
                            onChatClick={handleChatClick}
                        />
                    </ResizablePanel>

                    <ResizableHandle />

                    {/* Right Sidebar - Metadata */}
                    <ResizablePanel defaultSize={25} minSize={20} maxSize={40}>
                        <ProjectMetadataSidebar selectedProject={selectedProject} />
                    </ResizablePanel>
                </ResizablePanelGroup>
            </div>
        </div>
    );
};
