/**
 * Example Component: How to use React Query hooks for projects
 *
 * This file demonstrates the usage patterns for the new React Query hooks.
 * You can use this as a reference when migrating from Context-based data fetching.
 */

import { useState } from "react";
import { useProjects, useProjectArtifacts, useCreateProject, useUpdateProject, useDeleteProject, useAddFilesToProject, useRemoveFileFromProject } from "./hooks";
import type { CreateProjectRequest, UpdateProjectData } from "@/lib/types/projects";

/**
 * Example 1: Display a list of projects
 */
export function ProjectList() {
    const { data, isLoading, error, refetch } = useProjects();

    if (isLoading) {
        return <div>Loading projects...</div>;
    }

    if (error) {
        return <div>Error: {error.message}</div>;
    }

    return (
        <div>
            <h2>Projects ({data?.total})</h2>
            <button onClick={() => refetch()}>Refresh</button>
            <ul>
                {data?.projects.map(project => (
                    <li key={project.id}>
                        {project.name} - {project.description}
                    </li>
                ))}
            </ul>
        </div>
    );
}

/**
 * Example 2: Create a new project
 */
export function CreateProjectForm() {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const { mutate, isPending, error } = useCreateProject();

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const projectData: CreateProjectRequest = {
            name,
            description,
        };

        mutate(projectData, {
            onSuccess: newProject => {
                console.log("Project created:", newProject);
                setName("");
                setDescription("");
            },
            onError: error => {
                console.error("Failed to create project:", error);
            },
        });
    };

    return (
        <form onSubmit={handleSubmit}>
            <h2>Create New Project</h2>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Project name" required />
            <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)" />
            <button type="submit" disabled={isPending}>
                {isPending ? "Creating..." : "Create Project"}
            </button>
            {error && <div className="error">{error.message}</div>}
        </form>
    );
}

/**
 * Example 3: Update a project
 */
export function UpdateProjectForm({ projectId, currentName, currentDescription }: { projectId: string; currentName: string; currentDescription?: string }) {
    const [name, setName] = useState(currentName);
    const [description, setDescription] = useState(currentDescription || "");
    const { mutate, isPending } = useUpdateProject();

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const data: UpdateProjectData = {
            name,
            description,
        };

        mutate(
            { projectId, data },
            {
                onSuccess: () => {
                    console.log("Project updated successfully");
                },
            }
        );
    };

    return (
        <form onSubmit={handleSubmit}>
            <input type="text" value={name} onChange={e => setName(e.target.value)} />
            <textarea value={description} onChange={e => setDescription(e.target.value)} />
            <button type="submit" disabled={isPending}>
                {isPending ? "Updating..." : "Update"}
            </button>
        </form>
    );
}

/**
 * Example 4: Delete a project with confirmation
 */
export function DeleteProjectButton({ projectId }: { projectId: string }) {
    const { mutate, isPending } = useDeleteProject();

    const handleDelete = () => {
        if (confirm("Are you sure you want to delete this project?")) {
            mutate(projectId, {
                onSuccess: () => {
                    console.log("Project deleted successfully");
                },
                onError: error => {
                    console.error("Failed to delete project:", error);
                },
            });
        }
    };

    return (
        <button onClick={handleDelete} disabled={isPending} className="danger">
            {isPending ? "Deleting..." : "Delete Project"}
        </button>
    );
}

/**
 * Example 5: Display project artifacts and add/remove files
 */
export function ProjectArtifacts({ projectId }: { projectId: string }) {
    const { data: artifacts, isLoading, error } = useProjectArtifacts(projectId);
    const addFiles = useAddFilesToProject();
    const removeFile = useRemoveFileFromProject();

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length === 0) return;

        addFiles.mutate(
            { projectId, files },
            {
                onSuccess: () => {
                    console.log("Files uploaded successfully");
                    e.target.value = ""; // Reset input
                },
                onError: error => {
                    console.error("Failed to upload files:", error);
                },
            }
        );
    };

    const handleRemoveFile = (filename: string) => {
        removeFile.mutate({ projectId, filename });
    };

    if (isLoading) return <div>Loading artifacts...</div>;
    if (error) return <div>Error: {error.message}</div>;

    return (
        <div>
            <h3>Project Files</h3>
            <input type="file" multiple onChange={handleFileUpload} disabled={addFiles.isPending} />
            {addFiles.isPending && <div>Uploading...</div>}

            <ul>
                {artifacts?.map(artifact => (
                    <li key={artifact.filename}>
                        {artifact.filename}
                        <button onClick={() => handleRemoveFile(artifact.filename)} disabled={removeFile.isPending}>
                            Remove
                        </button>
                    </li>
                ))}
            </ul>
        </div>
    );
}

/**
 * Example 6: Combining multiple hooks in one component
 */
export function ProjectDetailView({ projectId }: { projectId: string }) {
    const { data: allProjects } = useProjects();
    const { data: artifacts } = useProjectArtifacts(projectId);
    const updateProject = useUpdateProject();
    const deleteProject = useDeleteProject();

    const project = allProjects?.projects.find(p => p.id === projectId);

    if (!project) {
        return <div>Project not found</div>;
    }

    return (
        <div>
            <h1>{project.name}</h1>
            <p>{project.description}</p>
            <p>Files: {artifacts?.length || 0}</p>

            <button
                onClick={() => {
                    updateProject.mutate({
                        projectId,
                        data: { name: project.name, description: "Updated description" },
                    });
                }}
            >
                Update
            </button>

            <button
                onClick={() => {
                    deleteProject.mutate(projectId);
                }}
            >
                Delete
            </button>
        </div>
    );
}
