import React, { useState, useEffect } from "react";
import { Info, Settings, User, HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";

import { Button, Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger, Tooltip, TooltipContent, TooltipTrigger, VisuallyHidden } from "@/lib/components/ui";
import { ProfileSettings } from "./ProfileSettings";
import { AccountSettings } from "./AccountSettings";
import { HelpSettings } from "./HelpSettings";
import { AboutProduct } from "@/lib/components/settings/AboutProduct";

export type SettingsSection = "profile" | "settings" | "help" | "about";

interface SidebarItemProps {
    icon: React.ReactNode;
    label: string;
    active: boolean;
    onClick: () => void;
}

const SidebarItem: React.FC<SidebarItemProps> = ({ icon, label, active, onClick }) => {
    return (
        <button onClick={onClick} className={cn("flex w-full cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors", active ? "dark:bg-accent bg-[var(--color-brand-w10)]" : "text-muted-foreground hover:bg-accent/50")}>
            {icon}
            <span>{label}</span>
        </button>
    );
};

interface SettingsDialogProps {
    iconOnly?: boolean;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    initialSection?: SettingsSection;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ iconOnly = false, open: controlledOpen, onOpenChange, initialSection = "profile" }) => {
    const [internalOpen, setInternalOpen] = useState(false);
    const [activeSection, setActiveSection] = useState<SettingsSection>(initialSection);

    // Use controlled state if provided, otherwise use internal state
    const isControlled = controlledOpen !== undefined;
    const open = isControlled ? controlledOpen : internalOpen;
    const setOpen = onOpenChange || setInternalOpen;

    // Update active section when dialog opens with a different initial section
    useEffect(() => {
        if (open) {
            setActiveSection(initialSection);
        }
    }, [open, initialSection]);

    const renderContent = () => {
        switch (activeSection) {
            case "profile":
                return <ProfileSettings />;
            case "settings":
                return <AccountSettings />;
            case "help":
                return <HelpSettings />;
            case "about":
                return <AboutProduct />;
            default:
                return <ProfileSettings />;
        }
    };

    const getSectionTitle = () => {
        switch (activeSection) {
            case "profile":
                return "Profile";
            case "settings":
                return "Settings";
            case "help":
                return "Help & Documentation";
            case "about":
                return "About";
            default:
                return "Settings";
        }
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            {/* When controlled externally (open prop is provided), don't render trigger */}
            {!isControlled &&
                (iconOnly ? (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <DialogTrigger asChild>
                                <button
                                    type="button"
                                    className="relative mx-auto flex w-full cursor-pointer flex-col items-center bg-[var(--color-primary-w100)] px-3 py-5 text-xs text-[var(--color-primary-text-w10)] transition-colors hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)]"
                                    aria-label="Open Settings"
                                >
                                    <Settings className="h-6 w-6" />
                                </button>
                            </DialogTrigger>
                        </TooltipTrigger>
                        <TooltipContent side="right">Settings</TooltipContent>
                    </Tooltip>
                ) : (
                    <DialogTrigger asChild>
                        <Button variant="outline" className="w-full justify-start gap-2">
                            <Settings className="size-5" />
                            <span>Settings</span>
                        </Button>
                    </DialogTrigger>
                ))}
            <DialogContent className="max-h-[90vh] w-[90vw] !max-w-[1200px] gap-0 p-0" showCloseButton={true}>
                <VisuallyHidden>
                    <DialogTitle>Settings</DialogTitle>
                    <DialogDescription>Configure application settings</DialogDescription>
                </VisuallyHidden>
                <div className="flex h-[80vh] overflow-hidden">
                    {/* Sidebar */}
                    <div className="bg-muted/30 flex w-64 flex-col border-r">
                        <div className="flex h-15 items-center px-4 text-lg font-semibold">Settings</div>

                        <nav className="flex flex-1 flex-col">
                            {/* Top items, scrollable */}
                            <div className="flex-1 space-y-1 overflow-y-auto">
                                <SidebarItem icon={<User className="size-4" />} label="Profile" active={activeSection === "profile"} onClick={() => setActiveSection("profile")} />
                                <SidebarItem icon={<Settings className="size-4" />} label="Settings" active={activeSection === "settings"} onClick={() => setActiveSection("settings")} />
                                <SidebarItem icon={<HelpCircle className="size-4" />} label="Help & Documentation" active={activeSection === "help"} onClick={() => setActiveSection("help")} />
                            </div>
                            {/* Bottom items, static */}
                            <div className="space-y-1 pb-2">
                                {/* Divider */}
                                <div className="mt-4 border-t pb-2" />
                                {/* About entry */}
                                <SidebarItem icon={<Info className="size-4" />} label="About" active={activeSection === "about"} onClick={() => setActiveSection("about")} />
                            </div>
                        </nav>
                    </div>

                    {/* Main Content */}
                    <div className="flex min-w-0 flex-1 flex-col">
                        {/* Header */}
                        <div className="flex items-center border-b px-6 py-4">
                            <h3 className="text-xl font-semibold">{getSectionTitle()}</h3>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 overflow-y-auto p-6">
                            <div className="mx-auto max-w-2xl">{renderContent()}</div>
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};
