import { Button, NavItem, type NavItemProps } from "@/lib/components/ui";
import { ChevronRight, Menu } from "lucide-react";
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
    const hasTabs = tabs && tabs.length > 0;
    return (
        <div className="border-b">
            <div className="relative flex max-h-[80px] min-h-[80px] w-full items-center px-4 md:px-8">
                {/* Breadcrumbs — full chain on desktop; collapsed to "… > current" on mobile */}
                {breadcrumbs &&
                    breadcrumbs.length > 0 &&
                    (() => {
                        const last = breadcrumbs[breadcrumbs.length - 1];
                        const parent = breadcrumbs.length > 1 ? breadcrumbs[breadcrumbs.length - 2] : null;
                        return (
                            <div className="absolute top-1 right-2 left-4 flex h-8 items-center md:right-auto md:left-8">
                                {/* Mobile: "… > current" */}
                                <div className="flex min-w-0 items-center md:hidden">
                                    {parent && (
                                        <>
                                            {parent.onClick ? (
                                                <Button variant="link" className="m-0 shrink-0 p-0" onClick={parent.onClick} aria-label={`Back to ${typeof parent.label === "string" ? parent.label : "previous"}`}>
                                                    …
                                                </Button>
                                            ) : (
                                                <span className="shrink-0">…</span>
                                            )}
                                            <span className="mx-1 shrink-0">
                                                <ChevronRight size={16} />
                                            </span>
                                        </>
                                    )}
                                    <div className="min-w-0 truncate">{last.label}</div>
                                </div>
                                {/* Desktop: full chain */}
                                <div className="hidden items-center md:flex">
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
                            </div>
                        );
                    })()}

                {/* Mobile nav drawer trigger — hidden on md+ where the persistent sidebar is visible */}
                <div className="mr-2 flex items-center pt-[35px] md:hidden">
                    <Button variant="ghost" onClick={() => window.dispatchEvent(new CustomEvent("open-mobile-nav"))} className="h-10 w-10 p-0" tooltip="Menu" aria-label="Open menu">
                        <Menu className="size-5" />
                    </Button>
                </div>

                {/* Leading Action */}
                {leadingAction && <div className="mr-4 flex items-center pt-[35px]">{leadingAction}</div>}

                {/* Title — flex-1 with min-w-0 lets it shrink and truncate so trailing buttons don't get pushed off narrow viewports */}
                <div className="min-w-0 flex-1 truncate pt-[35px] text-xl md:max-w-lg md:flex-none">{title}</div>

                {/* Nav Items — desktop only here; on mobile they render as a separate row below so they don't squeeze the title */}
                {hasTabs && (
                    <div className="scrollbar-hide ml-4 hidden min-w-0 items-center gap-4 overflow-x-auto pt-[35px] sm:gap-6 md:ml-8 md:flex" role="tablist">
                        {tabs.map(item => (
                            <div key={item.id} className="shrink-0">
                                <NavItem {...item} />
                            </div>
                        ))}
                    </div>
                )}

                {/* Spacer (only when title is fixed-width on md+) */}
                <div className="hidden flex-1 md:block" />

                {/* Buttons */}
                {buttons && buttons.length > 0 && (
                    <div className="ml-2 flex flex-shrink-0 items-center gap-2 pt-[35px]">
                        {buttons.map((button, index) => (
                            <React.Fragment key={index}>{button}</React.Fragment>
                        ))}
                    </div>
                )}
            </div>

            {/* Mobile tabs row — sits under the title row so tabs can scroll horizontally without competing for space */}
            {hasTabs && (
                <div className="scrollbar-hide flex items-center gap-4 overflow-x-auto px-4 pb-2 md:hidden" role="tablist">
                    {tabs.map(item => (
                        <div key={item.id} className="shrink-0">
                            <NavItem {...item} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
