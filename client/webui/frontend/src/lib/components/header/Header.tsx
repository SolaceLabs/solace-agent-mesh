import React from "react";

export interface Tab {
    id: string;
    label: string;
    isActive: boolean;
    onClick: () => void;
}

export interface HeaderProps {
    title: string;
    tabs?: Tab[];
    buttons?: React.ReactNode[];
    leadingAction?: React.ReactNode;
}

export const Header: React.FC<HeaderProps> = ({ title, tabs, buttons, leadingAction }) => {
    return (
        <div className="flex max-h-[80px] min-h-[80px] w-full items-center border-b px-8">
            {/* Leading Action */}
            {leadingAction && <div className="mr-4 flex items-center pt-[35px]">{leadingAction}</div>}

            {/* Title */}
            <div className="truncate pt-[35px] text-xl text-nowrap">{title}</div>

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
                <div className="flex items-center gap-2">
                    {buttons.map((button, index) => (
                        <React.Fragment key={index}>{button}</React.Fragment>
                    ))}
                </div>
            )}
        </div>
    );
};
