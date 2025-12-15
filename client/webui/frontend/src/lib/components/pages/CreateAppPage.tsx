import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Header, Input, Textarea } from "@/lib/components";
import { Loader2 } from "lucide-react";

export function CreateAppPage() {
    const navigate = useNavigate();
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [instructions, setInstructions] = useState("");
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
            const workspaceId = appData.workspaceId || appId;

            // Build initial message
            let initialMessage = `I'm starting a new app called "${name.trim()}".`;

            if (description.trim()) {
                initialMessage += `\n\nDescription: ${description.trim()}`;
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

            // Navigate to app editor with initial message in state
            navigate(`/apps/${appId}/edit`, {
                state: { initialMessage }
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
                    <form onSubmit={handleSubmit} className="space-y-6">
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
