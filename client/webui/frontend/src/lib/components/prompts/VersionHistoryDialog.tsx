/**
 * VersionHistoryDialog Component
 * Shows version history for a prompt group and allows restoring previous versions
 */

import React, { useState, useEffect } from 'react';
import { History, Check } from 'lucide-react';
import type { PromptGroup, Prompt } from '@/lib/types/prompts';
import { Dialog, DialogContent, DialogHeader, DialogTitle, Button } from '@/lib/components/ui';
import { formatPromptDate } from '@/lib/utils/promptUtils';
import { PromptRestoreDialog } from './PromptRestoreDialog';

interface VersionHistoryDialogProps {
    group: PromptGroup;
    onClose: () => void;
    onRestore: (promptId: string) => void;
}

export const VersionHistoryDialog: React.FC<VersionHistoryDialogProps> = ({
    group,
    onClose,
    onRestore,
}) => {
    const [versions, setVersions] = useState<Prompt[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedVersion, setSelectedVersion] = useState<Prompt | null>(null);
    const [restoringVersion, setRestoringVersion] = useState<Prompt | null>(null);

    useEffect(() => {
        const fetchVersions = async () => {
            setIsLoading(true);
            try {
                const response = await fetch(`/api/v1/prompts/groups/${group.id}/prompts`, {
                    credentials: 'include',
                });
                
                if (response.ok) {
                    const data = await response.json();
                    setVersions(data);
                }
            } catch (error) {
                console.error('Failed to fetch versions:', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchVersions();
    }, [group.id]);

    const handleRestoreClick = (prompt: Prompt) => {
        setRestoringVersion(prompt);
    };

    const handleRestoreConfirm = () => {
        if (restoringVersion) {
            onRestore(restoringVersion.id);
            setRestoringVersion(null);
            onClose();
        }
    };

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <History className="size-5" />
                        Version History: {group.name}
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 overflow-auto">
                    {isLoading ? (
                        <div className="flex items-center justify-center p-8">
                            <div className="size-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                        </div>
                    ) : versions.length === 0 ? (
                        <div className="p-8 text-center text-sm text-[var(--muted-foreground)]">
                            No versions found
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {versions.map((version) => {
                                const isProduction = version.id === group.production_prompt_id;
                                const isSelected = selectedVersion?.id === version.id;
                                
                                return (
                                    <div
                                        key={version.id}
                                        className={`rounded-lg border p-4 transition-colors cursor-pointer ${
                                            isSelected
                                                ? 'border-[var(--primary)] bg-[var(--primary)]/5'
                                                : 'border-[var(--border)] hover:border-[var(--primary)]/50'
                                        }`}
                                        onClick={() => setSelectedVersion(isSelected ? null : version)}
                                    >
                                        <div className="flex items-start justify-between gap-4 mb-3">
                                            <div className="flex items-center gap-2">
                                                <span className="font-semibold text-sm">
                                                    Version {version.version}
                                                </span>
                                                {isProduction && (
                                                    <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
                                                        <Check className="size-3" />
                                                        Production
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-[var(--muted-foreground)]">
                                                    {formatPromptDate(version.created_at)}
                                                </span>
                                                {!isProduction && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleRestoreClick(version);
                                                        }}
                                                        className="h-7 text-xs"
                                                    >
                                                        Restore
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {/* Show full text when selected, preview when not */}
                                        <div className={`rounded-md bg-[var(--muted)]/50 p-3 font-mono text-xs ${
                                            isSelected ? '' : 'line-clamp-3'
                                        }`}>
                                            <pre className="whitespace-pre-wrap break-words">
                                                {version.prompt_text}
                                            </pre>
                                        </div>
                                        
                                        {!isSelected && (
                                            <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                                                Click to expand
                                            </p>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t">
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                </div>
            </DialogContent>

            {/* Restore Confirmation Dialog */}
            {restoringVersion && (
                <PromptRestoreDialog
                    isOpen={true}
                    onClose={() => setRestoringVersion(null)}
                    onConfirm={handleRestoreConfirm}
                    versionNumber={restoringVersion.version}
                />
            )}
        </Dialog>
    );
};