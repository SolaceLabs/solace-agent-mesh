import { Button } from "@/lib/components/ui";
import { ChevronRight } from "lucide-react";
import React from "react";

export interface BreadcrumbItem {
    label: string;
    onClick?: () => void;
}

export interface Tab {
    id: string;
    label: string;
    isActive: boolean;
    onClick: () => void;
}

export interface HeaderProps {
    title: string | React.ReactNode;
    breadcrumbs?: BreadcrumbItem[];
    tabs?: Tab[];
    buttons?: React.ReactNode[];
    leadingAction?: React.ReactNode;
}

export const Header: React.FC<HeaderProps> = ({ title, breadcrumbs, tabs, buttons, leadingAction }) => {
    return (
        <div className="relative flex max-h-[80px] min-h-[80px] w-full items-center border-b px-8">
            {/* Breadcrumbs */}
            {breadcrumbs && breadcrumbs.length > 0 && (
                <div className="absolute top-1 left-8 flex h-8 items-center">
                    {breadcrumbs.map((crumb, index) => (
                        <React.Fragment key={index}>
                            {index > 0 && (
                                <span className="mx-1">
                                    <ChevronRight size={16} />
                                </span>
                            )}
                            {crumb.onClick ? (
                                <Button variant="link" className="m-0 p-0" onClick={crumb.onClick}>
                                    {crumb.label}
                                </Button>
                            ) : (
                                <div className="max-w-[150px] truncate">{crumb.label}</div>
                            )}
                        </React.Fragment>
                    ))}
                </div>
            )}

            {/* Leading Action */}
            {leadingAction && <div className="mr-4 flex items-center pt-[35px]">{leadingAction}</div>}

            {/* Title */}
            <div className="max-w-lg truncate pt-[35px] text-xl">{title}</div>

            {/* Tabs */}
            {tabs && tabs.length > 0 && (
                <div className="ml-8 flex items-center pt-[35px]" role="tablist">
                    {tabs.map((tab, index) => (
                        <button
                            key={tab.id}
                            role="tab"
                            aria-selected={tab.isActive}
                            onClick={tab.onClick}
                            className={`relative cursor-pointer px-4 py-3 font-medium transition-colors duration-200 ${tab.isActive ? "border-b-2 border-[var(--color-brand-wMain)] font-semibold" : ""} ${index > 0 ? "ml-6" : ""}`}
                        >
                            {tab.label}
                            {tab.isActive && <div className="absolute right-0 bottom-0 left-0 h-0.5" />}
                        </button>
                    ))}
                </div>
            )}

            {/* Spacer */}
            <div className="flex-1" />

            {/* Buttons */}
            {buttons && buttons.length > 0 && (
                <div className="flex items-center gap-2 pt-[35px]">
                    {buttons.map((button, index) => (
                        <React.Fragment key={index}>{button}</React.Fragment>
                    ))}
                </div>
            )}
        </div>
    );
};
