import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { RefreshCcw, Upload } from "lucide-react";

import { useChatContext } from "@/lib/hooks";
import type { SkillSummary, Skill } from "@/lib/types/skills";
import { Button, EmptyState, Header } from "@/lib/components";
import { SkillCards, SkillImportDialog } from "@/lib/components/skills";
import { authenticatedFetch, downloadBlob } from "@/lib/utils";

/**
 * Main page for viewing and managing skills
 */
export const SkillsPage: React.FC = () => {
    const navigate = useNavigate();
    const { addNotification } = useChatContext();
    const [skills, setSkills] = useState<SkillSummary[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showImportDialog, setShowImportDialog] = useState(false);

    // Fetch skills
    const fetchSkills = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch("/api/v1/skills", {
                credentials: "include",
            });
            if (response.ok) {
                const data = await response.json();
                setSkills(data.skills || []);
            } else {
                const errorData = await response.json().catch(() => ({ detail: "Failed to fetch skills" }));
                setError(errorData.detail || errorData.message || "Failed to fetch skills");
            }
        } catch (err) {
            console.error("Failed to fetch skills:", err);
            setError("Failed to connect to the server");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchSkills();
    }, []);

    // Handle use in chat
    const handleUseInChat = (skill: Skill) => {
        // Navigate to chat with skill context
        // Use a timestamp key to force re-render even if already on /chat
        navigate("/chat", {
            state: {
                skillId: skill.id,
                skillName: skill.name,
                skillDescription: skill.description,
                timestamp: Date.now(), // Force state change detection
            },
        });
        addNotification(`Using skill: ${skill.name}`, "info");
    };

    // Handle export skill (ZIP format by default for skill package compatibility)
    const handleExport = async (skill: Skill) => {
        try {
            // Use ZIP format for full skill package compatibility (includes scripts/, resources/)
            const response = await authenticatedFetch(`/api/v1/skills/${skill.id}/export?format=zip`);

            if (response.ok) {
                const blob = await response.blob();
                // Sanitize skill name for filename
                const safeName = skill.name.replace(/[^\w-]/g, "-");
                const filename = `${safeName}.skill.zip`;
                downloadBlob(blob, filename);
                addNotification("Skill exported successfully", "success");
            } else {
                const errorData = await response.json().catch(() => ({ detail: "Failed to export skill" }));
                addNotification(errorData.detail || "Failed to export skill", "error");
            }
        } catch (err) {
            console.error("Failed to export skill:", err);
            addNotification("Failed to export skill", "error");
        }
    };

    // Handle import skill
    const handleImport = async (file: File, options: { scope: string; ownerAgent?: string }) => {
        const formData = new FormData();
        formData.append("file", file);

        const queryParams = new URLSearchParams({
            scope: options.scope,
        });
        if (options.ownerAgent) {
            queryParams.append("owner_agent", options.ownerAgent);
        }

        const response = await authenticatedFetch(`/api/v1/skills/import/file?${queryParams.toString()}`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Failed to import skill" }));
            throw new Error(errorData.detail || "Failed to import skill");
        }

        const result = await response.json();

        // Show warnings if any
        if (result.warnings && result.warnings.length > 0) {
            addNotification(result.warnings.join(", "), "info");
        }

        // Show bundled resources info if imported from ZIP
        const resourceInfo = [];
        if (result.references_count > 0) resourceInfo.push(`${result.references_count} references`);
        if (result.scripts_count > 0) resourceInfo.push(`${result.scripts_count} scripts`);
        if (result.assets_count > 0) resourceInfo.push(`${result.assets_count} assets`);

        const resourceMsg = resourceInfo.length > 0 ? ` (with ${resourceInfo.join(", ")})` : "";
        addNotification(`Skill "${result.name}" imported successfully${resourceMsg}`, "success");
        await fetchSkills();
    };

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Skills"
                buttons={[
                    <Button key="importSkill" variant="ghost" title="Import Skill" onClick={() => setShowImportDialog(true)}>
                        <Upload className="size-4" />
                        Import Skill
                    </Button>,
                    <Button key="refreshSkills" data-testid="refreshSkills" disabled={isLoading} variant="ghost" title="Refresh Skills" onClick={() => fetchSkills()}>
                        <RefreshCcw className="size-4" />
                        Refresh Skills
                    </Button>,
                ]}
            />

            {isLoading ? (
                <EmptyState title="Loading skills..." variant="loading" />
            ) : error ? (
                <EmptyState
                    title="Failed to Load Skills"
                    subtitle={error}
                    variant="error"
                    buttons={[
                        {
                            text: "Retry",
                            variant: "default",
                            onClick: fetchSkills,
                        },
                    ]}
                />
            ) : (
                <div className="relative flex-1 p-4">
                    <SkillCards skills={skills} onUseInChat={handleUseInChat} onExport={handleExport} />
                </div>
            )}

            {/* Import Dialog */}
            <SkillImportDialog open={showImportDialog} onOpenChange={setShowImportDialog} onImport={handleImport} />
        </div>
    );
};
