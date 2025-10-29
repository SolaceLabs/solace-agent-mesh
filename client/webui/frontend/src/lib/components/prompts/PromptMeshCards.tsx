import React, { useState } from "react";

import type { PromptGroup } from "@/lib/types/prompts";

import { PromptDisplayCard } from "./PromptDisplayCard";
import { CreatePromptCard } from "./CreatePromptCard";
import { EmptyState } from "../common";

interface PromptMeshCardsProps {
    prompts: PromptGroup[];
    onManualCreate: () => void;
    onAIAssisted: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
}

export const PromptMeshCards: React.FC<PromptMeshCardsProps> = ({
    prompts,
    onManualCreate,
    onAIAssisted,
    onEdit,
    onDelete,
    onViewVersions
}) => {
    const [expandedPromptId, setExpandedPromptId] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");

    const handleToggleExpand = (promptId: string) => {
        setExpandedPromptId(prev => (prev === promptId ? null : promptId));
    };

    const filteredPrompts = prompts.filter(prompt => 
        prompt.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        prompt.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        prompt.command?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="h-full w-full pt-12 pl-12">
            <input 
                type="text" 
                data-testid="promptSearchInput" 
                placeholder="Search..." 
                value={searchQuery} 
                onChange={e => setSearchQuery(e.target.value)} 
                className="bg-background mb-4 rounded-md border px-3 py-2" 
            />

            {filteredPrompts.length === 0 && searchQuery ? (
                <EmptyState 
                    title="No prompts match your search" 
                    variant="noImage" 
                    buttons={[{ 
                        text: "Clear Search", 
                        variant: "default", 
                        onClick: () => setSearchQuery("") 
                    }]} 
                />
            ) : (
                <div className="max-h-[calc(100vh-250px)] overflow-y-auto">
                    <div className="flex flex-wrap gap-10">
                        {/* Create New Prompt Card - Always first */}
                        <CreatePromptCard 
                            onManualCreate={onManualCreate}
                            onAIAssisted={onAIAssisted}
                        />
                        
                        {/* Existing Prompt Cards */}
                        {filteredPrompts.map(prompt => (
                            <PromptDisplayCard
                                key={prompt.id}
                                prompt={prompt}
                                isExpanded={expandedPromptId === prompt.id}
                                onToggleExpand={() => handleToggleExpand(prompt.id)}
                                onEdit={onEdit}
                                onDelete={onDelete}
                                onViewVersions={onViewVersions}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};