import React from "react";
import { Plus } from "lucide-react";

import { CardContent } from "@/lib/components/ui";
import { GridCard } from "../common/GridCard";

interface CreateProjectCardProps {
    onClick: () => void;
}

export const CreateProjectCard: React.FC<CreateProjectCardProps> = ({ onClick }) => {
    return (
        <GridCard className="border border-dashed border-(--primary-wMain)" onClick={onClick} data-testid="createProjectCard">
            <CardContent className="flex h-full items-center justify-center">
                <div className="text-center">
                    <div className="mb-4 flex justify-center">
                        <div className="rounded-full bg-(--primary-w10) p-4">
                            <Plus className="h-8 w-8 text-(--primary-wMain)" />
                        </div>
                    </div>
                    <h3 className="text-lg font-semibold text-(--primary-text-wMain)">Create New Project</h3>
                </div>
            </CardContent>
        </GridCard>
    );
};
