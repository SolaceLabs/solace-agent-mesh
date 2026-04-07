# API Endpoint Pattern

Every API resource lives in its own folder under `src/lib/api/<resource>/` with four files:

```text
src/lib/api/<resource>/
├── service.ts   # Raw API calls
├── keys.ts      # TanStack Query cache keys
├── hooks.ts     # React hooks (queries + mutations)
└── index.ts     # Barrel re-export
```

Reference implementation: `src/lib/api/projects/`

## 1. service.ts

Async functions that call the centralized API client. Two base URLs are available:

- `api.webui.*` — WebUI backend routes (`src/lib/api/client.ts:19`)
- `api.platform.*` — Platform API routes (`src/lib/api/client.ts:20`)

```ts
// src/lib/api/projects/service.ts:6
export const getProjects = async () => {
    return api.webui.get<{ projects: Project[]; total: number }>("/api/v1/projects?include_artifact_count=true");
};

export const createProject = async (data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);
    return api.webui.post<Project>("/api/v1/projects", formData);
};

export const deleteProject = async (projectId: string) => {
    await api.webui.delete(`/api/v1/projects/${projectId}`);
};
```

Methods: `get`, `post`, `put`, `delete`, `patch` — all generic-typed.

For responses that need headers (e.g. SSE location): pass `{ fullResponse: true }` to get the raw `Response` object.

## 2. keys.ts

Hierarchical cache key factories using `as const`. Enables fine-grained invalidation.

```ts
// src/lib/api/projects/keys.ts:5
export const projectKeys = {
    all: ["projects"] as const,
    lists: () => [...projectKeys.all, "list"] as const,
    details: () => [...projectKeys.all, "detail"] as const,
    detail: (id: string) => [...projectKeys.details(), id] as const,
    artifacts: (id: string) => [...projectKeys.detail(id), "artifacts"] as const,
};
```

## 3. hooks.ts

React hooks wrapping service functions with TanStack Query.

**Queries** — for reading data:

```ts
// src/lib/api/projects/hooks.ts:21
export function useProjects() {
    return useQuery({
        queryKey: projectKeys.lists(),
        queryFn: projectService.getProjects,
        refetchOnMount: "always",
    });
}
```

Use `skipToken` for conditional queries when an ID may be null (`src/lib/api/projects/hooks.ts:33`).

**Mutations** — for create/update/delete, with cache invalidation:

```ts
// src/lib/api/projects/hooks.ts:70
export function useCreateProject() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: CreateProjectRequest) => projectService.createProject(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}
```

After a mutation, invalidate the relevant query keys. Use `removeQueries` for deleted resources (`src/lib/api/projects/hooks.ts:99`).

## 4. index.ts

Barrel re-export everything:

```ts
export * from "./hooks";
export * from "./keys";
export * from "./service";
export * from "./types"; // if you have a types.ts
```

## Adding a new API module

1. Create `src/lib/api/<resource>/` with the four files above
2. Define types in `types.ts` or in `src/lib/types/`
3. Wire service functions to `api.webui.*` or `api.platform.*`
4. Build cache keys following the hierarchical pattern
5. Wrap with `useQuery` / `useMutation` hooks
6. Re-export from `src/lib/api/index.ts`
