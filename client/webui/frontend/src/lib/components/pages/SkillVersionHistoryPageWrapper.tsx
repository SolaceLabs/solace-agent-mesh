import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { SkillVersionHistoryPage } from "../skills/SkillVersionHistoryPage";
import { EmptyState } from "../common";
import * as versionedSkillsApi from "@/lib/services/versionedSkillsApi";
import type { SkillGroup } from "@/lib/types/skills";

/**
 * Wrapper page for skill version history that fetches the skill group data
 * and passes it to the SkillVersionHistoryPage component.
 */
export const SkillVersionHistoryPageWrapper: React.FC = () => {
    const { skillId } = useParams<{ skillId: string }>();
    const navigate = useNavigate();
    const [skillGroup, setSkillGroup] = useState<SkillGroup | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchSkillGroup = async () => {
            if (!skillId) {
                setError("No skill ID provided");
                setIsLoading(false);
                return;
            }

            try {
                setIsLoading(true);
                const group = await versionedSkillsApi.getSkillGroup(skillId, true);
                setSkillGroup(group);
            } catch (err) {
                console.error("Failed to fetch skill group:", err);
                setError("Failed to load skill group");
            } finally {
                setIsLoading(false);
            }
        };

        fetchSkillGroup();
    }, [skillId]);

    const handleBack = () => {
        navigate("/skills");
    };

    const handleBackToSkillDetail = () => {
        navigate("/skills");
    };

    const handleEdit = (group: SkillGroup) => {
        // Navigate to edit page (to be implemented)
        console.log("Edit skill group:", group.id);
    };

    const handleDeleteAll = (id: string, name: string) => {
        // Handle delete all versions (to be implemented)
        console.log("Delete all versions for:", id, name);
    };

    const handleRestoreVersion = async (versionId: string) => {
        if (!skillId) return;

        try {
            await versionedSkillsApi.rollbackToVersion(skillId, { versionId });
            // Refresh the skill group data
            const group = await versionedSkillsApi.getSkillGroup(skillId, true);
            setSkillGroup(group);
        } catch (err) {
            console.error("Failed to restore version:", err);
        }
    };

    if (isLoading) {
        return <EmptyState title="Loading skill versions..." variant="loading" />;
    }

    if (error || !skillGroup) {
        return (
            <EmptyState
                title="Failed to Load Skill"
                subtitle={error || "Skill not found"}
                variant="error"
                buttons={[
                    {
                        text: "Back to Skills",
                        variant: "default",
                        onClick: handleBack,
                    },
                ]}
            />
        );
    }

    return <SkillVersionHistoryPage group={skillGroup} onBack={handleBack} onBackToSkillDetail={handleBackToSkillDetail} onEdit={handleEdit} onDeleteAll={handleDeleteAll} onRestoreVersion={handleRestoreVersion} />;
};
