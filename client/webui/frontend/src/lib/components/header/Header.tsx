import { Button, NavItem, type NavItemProps } from "@/lib/components/ui";
import { ChevronRight } from "lucide-react";
import React from "react";

export interface BreadcrumbItem {
    label: string;
    onClick?: () => void;
}

export interface HeaderProps {
    title: string | React.ReactNode;
    breadcrumbs?: BreadcrumbItem[];
    tabs?: NavItemProps[];
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

            {/* Nav Items */}
            {tabs && tabs.length > 0 && (
                <div className="ml-8 flex items-center gap-6 pt-[35px]" role="tablist">
                    {tabs.map(item => (
                        <NavItem key={item.id} {...item} />
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
