import React from "react";
import { Plus } from "lucide-react";

import { CardContent } from "@/lib/components/ui";
import { GridCard } from "../common/GridCard";

interface CreateProjectCardProps {
    onClick: () => void;
}

export const CreateProjectCard: React.FC<CreateProjectCardProps> = ({ onClick }) => {
    return (
        <GridCard className="border border-dashed border-[var(--color-primary-wMain)]" onClick={onClick} data-testid="createProjectCard">
            <CardContent className="flex h-full items-center justify-center">
                <div className="text-center">
                    <div className="mb-4 flex justify-center">
                        <div className="bg-primary/10 rounded-full p-4">
                            <Plus className="text-primary h-8 w-8" />
                        </div>
                    </div>
                    <h3 className="text-foreground text-lg font-semibold">Create New Project</h3>
                </div>
            </CardContent>
        </GridCard>
    );
};
