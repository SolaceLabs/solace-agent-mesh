import React from "react";
import { Plus } from "lucide-react";

import { Card, CardContent } from "@/lib/components/ui";

interface CreateProjectCardProps {
    onClick: () => void;
}

export const CreateProjectCard: React.FC<CreateProjectCardProps> = ({ onClick }) => {
    return (
        <Card
            className="h-[196px] w-full sm:w-[380px] flex-shrink-0 cursor-pointer transition-all duration-200 hover:shadow-lg bg-card border border-dashed border-muted-foreground/50 hover:border-primary hover:bg-accent/30"
            onClick={onClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onClick();
                }
            }}
        >
            <CardContent className="flex h-full items-center justify-center">
                <div className="text-center">
                    <div className="mb-4 flex justify-center">
                        <div className="rounded-full bg-primary/10 p-4">
                            <Plus className="h-8 w-8 text-primary" />
                        </div>
                    </div>
                    <h3 className="text-lg font-semibold text-foreground">
                        Create New Project
                    </h3>
                </div>
            </CardContent>
        </Card>
    );
};