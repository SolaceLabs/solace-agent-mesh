import React from "react";

import { Button } from "@/lib/components/ui";
import { PLUGIN_TYPES, pluginRegistry } from "@/lib/plugins";

interface LayoutSelectorProps {
    currentLayout: string;
    onLayoutChange: (layout: string) => void;
    className?: string;
}

// TBD: Move to enterprise
export const LayoutSelector: React.FC<LayoutSelectorProps> = ({ currentLayout, onLayoutChange, className = "" }) => {
    const layouts = pluginRegistry.getPluginsByType(PLUGIN_TYPES.LAYOUT);

    // Don't render if there are no layouts or only one layout
    return layouts && layouts.length > 1 ? (
        <div className={`flex items-center space-x-1 ${className}`}>
            <span className={`text-sm font-semibold`}>Layout:</span>
            <div className="flex gap-1 rounded-sm p-1">
                {layouts.map(layout => {
                    const Icon = layout.icon;
                    const isActive = currentLayout === layout.id;

                    return (
                        <Button variant="ghost" size="sm" key={layout.id} onClick={() => onLayoutChange(layout.id)} title={layout.label} className={isActive ? "bg-[var(--color-secondary-w20)] dark:bg-[var(--color-secondary-w80)]" : ""}>
                            {Icon && <Icon size={14} />}
                            <span>{layout.label}</span>
                        </Button>
                    );
                })}
            </div>
        </div>
    ) : null;
};
