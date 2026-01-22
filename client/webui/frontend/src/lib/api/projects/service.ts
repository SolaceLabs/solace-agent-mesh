import { api } from "@/lib/api";
import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData, UploadProgress, UploadFilesResult, ArtifactStreamEventData } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";
import { getAccessToken } from "@/lib/utils/api";

export const getProjects = async () => {
    const response = await api.webui.get<{ projects: Project[]; total: number }>("/api/v1/projects?include_artifact_count=true");
    return response;
};

export const createProject = async (data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);

    if (data.description) {
        formData.append("description", data.description);
    }

    const response = await api.webui.post<Project>("/api/v1/projects", formData);
    return response;
};

/**
 * Upload files to project using streaming API with SSE progress tracking
 * @param projectId - Project UUID
 * @param files - Files to upload
 * @param fileMetadata - Optional descriptions per file
 * @param onProgress - Callback for progress updates
 * @returns Promise resolving to upload result
 */
export const addFilesToProjectStream = async (projectId: string, files: File[], fileMetadata: Record<string, string> | undefined, onProgress?: (progress: UploadProgress) => void): Promise<UploadFilesResult> => {
    // 1. Build FormData
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));
    if (fileMetadata && Object.keys(fileMetadata).length > 0) {
        formData.append("fileMetadata", JSON.stringify(fileMetadata));
    }

    const response = await api.webui.post(`/api/v1/projects/${projectId}/artifacts_stream`, formData, { fullResponse: true });

    if (response.status !== 202) {
        throw new Error(`Upload initiation failed: ${response.statusText}`);
    }

    const result = await response.json();
    const uploadId = result.upload_id;

    if (!uploadId) {
        throw new Error("No upload_id returned from server");
    }

    // 3. Subscribe to SSE progress events
    return new Promise<UploadFilesResult>((resolve, reject) => {
        const accessToken = getAccessToken();
        const params = new URLSearchParams();
        if (accessToken) {
            params.append("token", accessToken);
        }

        const sseUrl = api.webui.getFullUrl(`/api/v1/sse/subscribe/${uploadId}`);
        const eventSourceUrl = params.toString() ? `${sseUrl}?${params}` : sseUrl;
        const eventSource = new EventSource(eventSourceUrl, { withCredentials: true });

        // Track progress state
        const progressState: UploadProgress = {
            phase: "validating",
            statusText: "Validating files...",
            fileCount: files.length,
            completedFiles: 0,
            failedFiles: [],
            succeededFiles: [],
        };

        const updateProgress = (updates: Partial<UploadProgress>) => {
            Object.assign(progressState, updates);
            onProgress?.(progressState);
        };

        const handleMessage = (event: MessageEvent) => {
            try {
                const data: ArtifactStreamEventData = JSON.parse(event.data);

                switch (data.type) {
                    case "validation_started":
                        updateProgress({
                            phase: "validating",
                            statusText: `Validating ${data.file_count} file(s)...`,
                        });
                        break;

                    case "validation_completed":
                        updateProgress({
                            phase: "saving",
                            statusText: "Validation complete",
                        });
                        break;

                    case "artifact_saving_started":
                        updateProgress({
                            phase: "saving",
                            statusText: `Saving ${data.file_count} file(s)...`,
                        });
                        break;

                    case "artifact_saved":
                        if (data.filename) {
                            progressState.succeededFiles.push(data.filename);
                            progressState.completedFiles = progressState.succeededFiles.length;
                            updateProgress({
                                statusText: `Saved: ${data.filename} ${data.progress || ""}`,
                            });
                        }
                        break;

                    case "indexing_started":
                        updateProgress({
                            phase: "indexing",
                            statusText: `Creating search indexes...`,
                        });
                        break;

                    case "index_creation_completed":
                        if (data.filename) {
                            updateProgress({
                                statusText: `Indexed: ${data.filename} ${data.progress || ""}`,
                            });
                        }
                        break;

                    case "index_creation_failed":
                        if (data.filename) {
                            // Index failure doesn't fail the entire upload
                            console.warn(`Index creation failed for ${data.filename}:`, data.error);
                        }
                        break;

                    case "upload_completed":
                        updateProgress({
                            phase: "completed",
                            statusText: "Upload complete!",
                        });
                        eventSource.close();
                        resolve({
                            success: true,
                            totalFiles: data.total_files || files.length,
                            succeededFiles: progressState.succeededFiles,
                            failedFiles: progressState.failedFiles,
                        });
                        break;

                    case "upload_failed":
                        updateProgress({
                            phase: "error",
                            statusText: `Upload failed: ${data.error || "Unknown error"}`,
                        });
                        eventSource.close();
                        reject(new Error(data.error || "Upload failed"));
                        break;
                }
            } catch (err) {
                console.error("Failed to parse SSE message:", err);
            }
        };

        // Event listeners
        eventSource.addEventListener("upload_progress", handleMessage);
        eventSource.addEventListener("upload_success", handleMessage);
        eventSource.addEventListener("upload_error", handleMessage);

        eventSource.onerror = () => {
            eventSource.close();
            reject(new Error("Connection lost during upload. Please try again."));
        };
    });
};

/**
 * @deprecated Use addFilesToProjectStream instead
 */
export const addFilesToProject = async (projectId: string, files: File[], fileMetadata?: Record<string, string>) => {
    const formData = new FormData();

    files.forEach(file => {
        formData.append("files", file);
    });

    if (fileMetadata && Object.keys(fileMetadata).length > 0) {
        formData.append("fileMetadata", JSON.stringify(fileMetadata));
    }

    const response = await api.webui.post(`/api/v1/projects/${projectId}/artifacts`, formData);
    return response;
};

export const removeFileFromProject = async (projectId: string, filename: string) => {
    const response = await api.webui.delete(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`);
    return response;
};

export const updateFileMetadata = async (projectId: string, filename: string, description: string) => {
    const formData = new FormData();
    formData.append("description", description);

    const response = await api.webui.patch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, formData);
    return response;
};

export const updateProject = async (projectId: string, data: UpdateProjectData) => {
    const response = await api.webui.put<Project>(`/api/v1/projects/${projectId}`, data);
    return response;
};

export const deleteProject = async (projectId: string) => {
    await api.webui.delete(`/api/v1/projects/${projectId}`);
};

export const getProjectArtifacts = async (projectId: string) => {
    const response = await api.webui.get<ArtifactInfo[]>(`/api/v1/projects/${projectId}/artifacts`);
    return response;
};

export const getProjectSessions = async (projectId: string) => {
    const response = await api.webui.get<PaginatedSessionsResponse>(`/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`);
    return response.data;
};

export const exportProject = async (projectId: string) => {
    const response = await api.webui.get(`/api/v1/projects/${projectId}/export`, { fullResponse: true });
    return await response.blob();
};

export const importProject = async (file: File, options: { preserveName: boolean; customName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("options", JSON.stringify(options));

    const result = await api.webui.post("/api/v1/projects/import", formData);
    return result;
};
