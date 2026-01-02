import React, { useState } from "react";
import { Info, Settings, Type, Volume2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { useConfigContext } from "@/lib/hooks";

import { Button, Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger, Tooltip, TooltipContent, TooltipTrigger, VisuallyHidden } from "@/lib/components/ui";
import { SpeechSettingsPanel } from "./SpeechSettings";
import { GeneralSettings } from "./GeneralSettings";
import { AboutProduct } from "@/lib/components/settings/AboutProduct";

type SettingsSection = "general" | "speech" | "about";

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
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ iconOnly = false, open: controlledOpen, onOpenChange }) => {
    const { configFeatureEnablement } = useConfigContext();
    const [internalOpen, setInternalOpen] = useState(false);
    const [activeSection, setActiveSection] = useState<SettingsSection>("general");

    // Use controlled state if provided, otherwise use internal state
    const isControlled = controlledOpen !== undefined;
    const open = isControlled ? controlledOpen : internalOpen;
    const setOpen = onOpenChange || setInternalOpen;

    // Feature flags
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;
    const ttsEnabled = configFeatureEnablement?.textToSpeech ?? true;
    const speechEnabled = sttEnabled || ttsEnabled;

    const renderContent = () => {
        switch (activeSection) {
            case "about":
                return <AboutProduct />;
            case "general":
                return <GeneralSettings />;
            case "speech":
                return <SpeechSettingsPanel />;
            default:
                return <GeneralSettings />;
        }
    };

    const getSectionTitle = () => {
        switch (activeSection) {
            case "about":
                return "About";
            case "general":
                return "General";
            case "speech":
                return "Speech";
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
                                <SidebarItem icon={<Type className="size-4" />} label="General" active={activeSection === "general"} onClick={() => setActiveSection("general")} />
                                {speechEnabled && <SidebarItem icon={<Volume2 className="size-4" />} label="Speech" active={activeSection === "speech"} onClick={() => setActiveSection("speech")} />}
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
