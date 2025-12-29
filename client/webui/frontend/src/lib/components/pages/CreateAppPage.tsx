import { useState, useRef, ChangeEvent, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Header, Input, Textarea } from "@/lib/components";
import { Loader2, Paperclip, X } from "lucide-react";
import { useDragAndDrop } from "@/lib/hooks";

export function CreateAppPage() {
    const navigate = useNavigate();
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [instructions, setInstructions] = useState("");
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileSelect = () => {
        if (!creating) {
            fileInputRef.current?.click();
        }
    };

    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files) {
            const newFiles = Array.from(files).filter(
                (newFile) =>
                    !selectedFiles.some(
                        (existingFile) =>
                            existingFile.name === newFile.name &&
                            existingFile.size === newFile.size &&
                            existingFile.lastModified === newFile.lastModified
                    )
            );
            if (newFiles.length > 0) {
                setSelectedFiles((prev) => [...prev, ...newFiles]);
            }
        }
        // Reset input so same file can be selected again
        if (event.target) {
            event.target.value = "";
        }
    };

    const handleRemoveFile = (index: number) => {
        setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const handleFilesDropped = useCallback(
        (files: File[]) => {
            const newFiles = files.filter(
                (newFile) =>
                    !selectedFiles.some(
                        (existingFile) =>
                            existingFile.name === newFile.name &&
                            existingFile.size === newFile.size &&
                            existingFile.lastModified === newFile.lastModified
                    )
            );
            if (newFiles.length > 0) {
                setSelectedFiles((prev) => [...prev, ...newFiles]);
            }
        },
        [selectedFiles]
    );

    const { isDragging, handleDragEnter, handleDragOver, handleDragLeave, handleDrop } = useDragAndDrop({
        onFilesDropped: handleFilesDropped,
        disabled: creating,
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!name.trim()) {
            setError("App name is required");
            return;
        }

        setCreating(true);
        setError(null);

        try {
            // Create app
            const appResponse = await fetch("/api/v1/apps", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    name: name.trim(),
                    description: description.trim() || undefined,
                }),
            });

            if (!appResponse.ok) {
                const errorData = await appResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || "Failed to create app");
            }

            const appData = await appResponse.json();
            const appId = appData.appId;

            // Upload files as artifacts if any were selected
            const artifactFilenames: string[] = [];
            let effectiveSessionId: string | null = null;

            for (const file of selectedFiles) {
                const formData = new FormData();
                formData.append("upload_file", file);
                formData.append("filename", file.name);
                if (effectiveSessionId) {
                    formData.append("sessionId", effectiveSessionId);
                }

                const uploadResponse = await fetch("/api/v1/artifacts/upload", {
                    method: "POST",
                    body: formData,
                });

                if (uploadResponse.ok) {
                    const uploadData = await uploadResponse.json();
                    if (!effectiveSessionId) {
                        effectiveSessionId = uploadData.sessionId;
                    }
                    artifactFilenames.push(uploadData.filename || file.name);
                } else {
                    console.warn(`Failed to upload file: ${file.name}`);
                }
            }

            // Build initial message
            let initialMessage = `I'm starting a new app called "${name.trim()}".`;

            if (description.trim()) {
                initialMessage += `\n\nDescription: ${description.trim()}`;
            }

            // Add uploaded files section if any files were uploaded
            if (artifactFilenames.length > 0) {
                initialMessage += `\n\nThe user has provided the following files in the user_input/ directory:`;
                for (const filename of artifactFilenames) {
                    initialMessage += `\n- ${filename}`;
                }
                initialMessage += `\n\nReview these files and incorporate as appropriate. Note: Files in user_input/ are for development only - copy any assets needed in the final app to public/.`;
            }

            if (instructions.trim()) {
                // User provided specific instructions
                initialMessage += `\n\nPlease code this with these instructions:\n${instructions.trim()}`;
            } else {
                // No instructions - ask agent to guide requirements gathering
                initialMessage += `\n\nPlease ask me questions about the requirements. Here are some suggestions to consider:
- What are the main features this app should have?
- What kind of data will it work with?
- Do you need to integrate with any SAM agents?
- What should the user interface look like?`;
            }

            // Navigate to app editor with initial message and session info in state
            navigate(`/apps/${appId}/edit`, {
                state: {
                    initialMessage,
                    sessionId: effectiveSessionId,
                    uploadedFiles: artifactFilenames,
                },
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setCreating(false);
        }
    };

    const handleCancel = () => {
        navigate("/apps");
    };

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Create New App"
                subtitle="Build a React application through conversation with the App Agent"
            />

            <div className="flex-1 overflow-auto p-6">
                <div className="mx-auto max-w-2xl">
                    <form
                        onSubmit={handleSubmit}
                        className={`space-y-6 rounded-lg border-2 p-6 transition-colors ${
                            isDragging
                                ? "border-dashed border-primary bg-primary/5"
                                : "border-transparent"
                        }`}
                        onDragEnter={handleDragEnter}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                    >
                        <div>
                            <label
                                htmlFor="app-name"
                                className="block text-sm font-medium mb-2"
                            >
                                App Name <span className="text-red-500">*</span>
                            </label>
                            <Input
                                id="app-name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="My Awesome App"
                                disabled={creating}
                                required
                                autoFocus
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="app-description"
                                className="block text-sm font-medium mb-2"
                            >
                                Description
                            </label>
                            <Textarea
                                id="app-description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Describe what your app should do..."
                                rows={4}
                                disabled={creating}
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="app-instructions"
                                className="block text-sm font-medium mb-2"
                            >
                                Tell me how your app should work and look
                            </label>
                            <Textarea
                                id="app-instructions"
                                value={instructions}
                                onChange={(e) => setInstructions(e.target.value)}
                                placeholder="Describe the features, UI/UX, data sources, or leave blank to be guided through requirements..."
                                rows={6}
                                disabled={creating}
                            />
                        </div>

                        {/* File Upload Section */}
                        <div>
                            <label className="block text-sm font-medium mb-2">
                                Reference Files (optional)
                            </label>
                            <p className="text-sm text-muted-foreground mb-3">
                                Upload mockups, sample data, or other files to help build your app.
                                You can also drag and drop files anywhere on this form.
                            </p>

                            {/* Hidden File Input */}
                            <input
                                type="file"
                                ref={fileInputRef}
                                className="hidden"
                                multiple
                                onChange={handleFileChange}
                                accept="*/*"
                                disabled={creating}
                            />

                            {/* Selected Files Display */}
                            {selectedFiles.length > 0 && (
                                <div className="mb-3 flex flex-wrap gap-2">
                                    {selectedFiles.map((file, index) => (
                                        <div
                                            key={`${file.name}-${file.lastModified}-${index}`}
                                            className="flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-1.5 text-sm"
                                        >
                                            <span className="max-w-[200px] truncate">
                                                {file.name}
                                            </span>
                                            <button
                                                type="button"
                                                onClick={() => handleRemoveFile(index)}
                                                className="text-muted-foreground hover:text-foreground"
                                                disabled={creating}
                                            >
                                                <X className="size-4" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Add Files Button */}
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleFileSelect}
                                disabled={creating}
                                className="gap-2"
                            >
                                <Paperclip className="size-4" />
                                {selectedFiles.length > 0 ? "Add More Files" : "Add Files"}
                            </Button>
                        </div>

                        {error && (
                            <div className="p-4 bg-destructive/10 text-destructive rounded-md text-sm">
                                {error}
                            </div>
                        )}

                        <div className="flex gap-3 justify-end">
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={handleCancel}
                                disabled={creating}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={creating || !name.trim()}
                            >
                                {creating && <Loader2 className="size-4 animate-spin mr-2" />}
                                {creating ? "Creating..." : "Create App and Start Coding"}
                            </Button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
