# React Query Migration Guide

This guide shows how to migrate from Context-based data fetching to React Query hooks.

## Overview

React Query has been integrated with the existing API client. The setup includes:

1. **Service Layer** (`src/lib/api/projects/service.ts`): Pure functions that make API calls using the `api` client
2. **Query Keys** (`src/lib/api/projects/keys.ts`): Centralized query key management for caching
3. **Hooks** (`src/lib/api/projects/hooks.ts`): React Query hooks for queries and mutations
4. **QueryClient** (`src/App.tsx`): Configured with sensible defaults

## Migration Examples

### Example 1: Fetching Projects

**Before (using Context):**

```tsx
import { useProjectContext } from "@/lib/providers";

function MyComponent() {
    const { projects, isLoading, error } = useProjectContext();

    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;

    return (
        <div>
            {projects.map(project => (
                <div key={project.id}>{project.name}</div>
            ))}
        </div>
    );
}
```

**After (using React Query):**

```tsx
import { useProjects } from "@/lib/api/projects";

function MyComponent() {
    const { data, isLoading, error } = useProjects();

    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error: {error.message}</div>;

    // data has shape { projects: Project[], total: number }
    return (
        <div>
            {data.projects.map(project => (
                <div key={project.id}>{project.name}</div>
            ))}
        </div>
    );
}
```

### Example 2: Creating a Project

**Before (using Context):**

```tsx
import { useProjectContext } from "@/lib/providers";

function CreateProjectForm() {
    const { createProject } = useProjectContext();

    const handleSubmit = async (formData: FormData) => {
        try {
            await createProject(formData);
            // Success!
        } catch (error) {
            // Handle error
        }
    };

    return <form onSubmit={handleSubmit}>...</form>;
}
```

**After (using React Query):**

```tsx
import { useCreateProject } from "@/lib/api/projects";

function CreateProjectForm() {
    const { mutate, isPending, error } = useCreateProject();

    const handleSubmit = (data: CreateProjectRequest) => {
        mutate(data, {
            onSuccess: () => {
                // Projects list will auto-refresh due to invalidation
                console.log("Project created!");
            },
            onError: error => {
                console.error("Failed to create project:", error);
            },
        });
    };

    return <form onSubmit={handleSubmit}>...</form>;
}
```

### Example 3: Updating a Project

**Before (using Context):**

```tsx
import { useProjectContext } from "@/lib/providers";

function EditProject({ projectId }: { projectId: string }) {
    const { updateProject } = useProjectContext();

    const handleUpdate = async (data: UpdateProjectData) => {
        try {
            await updateProject(projectId, data);
        } catch (error) {
            // Handle error
        }
    };

    return <button onClick={() => handleUpdate(data)}>Update</button>;
}
```

**After (using React Query):**

```tsx
import { useUpdateProject } from "@/lib/api/projects";

function EditProject({ projectId }: { projectId: string }) {
    const { mutate, isPending } = useUpdateProject();

    const handleUpdate = (data: UpdateProjectData) => {
        mutate({ projectId, data });
    };

    return (
        <button onClick={() => handleUpdate(data)} disabled={isPending}>
            {isPending ? "Updating..." : "Update"}
        </button>
    );
}
```

### Example 4: Deleting a Project

**Before (using Context):**

```tsx
import { useProjectContext } from "@/lib/providers";

function DeleteButton({ projectId }: { projectId: string }) {
    const { deleteProject } = useProjectContext();

    const handleDelete = async () => {
        try {
            await deleteProject(projectId);
        } catch (error) {
            // Handle error
        }
    };

    return <button onClick={handleDelete}>Delete</button>;
}
```

**After (using React Query):**

```tsx
import { useDeleteProject } from "@/lib/api/projects";

function DeleteButton({ projectId }: { projectId: string }) {
    const { mutate, isPending } = useDeleteProject();

    return (
        <button onClick={() => mutate(projectId)} disabled={isPending}>
            {isPending ? "Deleting..." : "Delete"}
        </button>
    );
}
```

### Example 5: Working with Project Artifacts

**New (React Query only):**

```tsx
import { useProjectArtifacts, useAddFilesToProject, useRemoveFileFromProject } from "@/lib/api/projects";

function ProjectArtifacts({ projectId }: { projectId: string }) {
    const { data: artifacts, isLoading } = useProjectArtifacts(projectId);
    const addFiles = useAddFilesToProject();
    const removeFile = useRemoveFileFromProject();

    const handleUpload = (files: File[]) => {
        addFiles.mutate({ projectId, files });
    };

    const handleRemove = (filename: string) => {
        removeFile.mutate({ projectId, filename });
    };

    if (isLoading) return <div>Loading artifacts...</div>;

    return (
        <div>
            {artifacts?.map(artifact => (
                <div key={artifact.filename}>
                    {artifact.filename}
                    <button onClick={() => handleRemove(artifact.filename)}>Remove</button>
                </div>
            ))}
        </div>
    );
}
```

## Available Hooks

### Query Hooks (for fetching data)

- `useProjects()` - Fetch all projects
- `useProjectArtifacts(projectId)` - Fetch artifacts for a project
- `useProjectSessions(projectId)` - Fetch sessions for a project

### Mutation Hooks (for modifying data)

- `useCreateProject()` - Create a new project
- `useUpdateProject()` - Update a project
- `useDeleteProject()` - Delete a project
- `useAddFilesToProject()` - Add files to a project
- `useRemoveFileFromProject()` - Remove a file from a project
- `useUpdateFileMetadata()` - Update file metadata
- `useExportProject()` - Export a project
- `useImportProject()` - Import a project

## Benefits of React Query

1. **Automatic Caching**: Data is cached and reused across components
2. **Background Refetching**: Keeps data fresh automatically
3. **Optimistic Updates**: UI can update before server confirms
4. **Request Deduplication**: Multiple components requesting same data = single request
5. **Better Error Handling**: Built-in error states and retry logic
6. **DevTools**: Install `@tanstack/react-query-devtools` for debugging

## Adding React Query DevTools (Optional)

Install the devtools:

```bash
npm install @tanstack/react-query-devtools
```

Add to App.tsx:

```tsx
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            {/* ... your app ... */}
            <ReactQueryDevtools initialIsOpen={false} />
        </QueryClientProvider>
    );
}
```

## Creating Hooks for Other Resources

Follow this pattern for other API resources:

1. Create a service file with pure API functions
2. Create a keys file for query key management
3. Create hooks using `useQuery` and `useMutation`
4. Export from an index file

Example structure:

```
src/lib/api/
├── client.ts          # Existing API client
├── projects/
│   ├── service.ts     # API functions
│   ├── keys.ts        # Query keys
│   ├── hooks.ts       # React Query hooks
│   └── index.ts       # Exports
└── sessions/          # Example of another resource
    ├── service.ts
    ├── keys.ts
    ├── hooks.ts
    └── index.ts
```
