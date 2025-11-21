import React, { useState } from "react";
import { Settings, Type, Volume2 } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogTrigger, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { DropdownMenuItem } from "@/lib/components/ui/dropdown-menu";
import { SpeechSettingsPanel } from "./SpeechSettings";
import { GeneralSettings } from "./GeneralSettings";
import { cn } from "@/lib/utils";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { useConfigContext } from "@/lib/hooks";

type SettingsSection = "general" | "speech";

interface SidebarItemProps {
    icon: React.ReactNode;
    label: string;
    value: SettingsSection;
    active: boolean;
    onClick: () => void;
}

const SidebarItem: React.FC<SidebarItemProps> = ({ icon, label, active, onClick }) => {
    return (
        <button
            onClick={onClick}
            className={cn("flex w-full cursor-pointer items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors", active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground")}
        >
            {icon}
            <span>{label}</span>
        </button>
    );
};

interface SettingsDialogProps {
    iconOnly?: boolean;
}

export const SettingsDialog: React.FC<SettingsDialogProps> = ({ iconOnly = false }) => {
    const { configFeatureEnablement } = useConfigContext();
    const [open, setOpen] = useState(false);
    const [activeSection, setActiveSection] = useState<SettingsSection>("general");

    // Feature flags
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;
    const ttsEnabled = configFeatureEnablement?.textToSpeech ?? true;
    const speechEnabled = sttEnabled || ttsEnabled;

    const renderContent = () => {
        switch (activeSection) {
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
            {iconOnly ? (
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
                    <DropdownMenuItem
                        className="cursor-pointer hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)] focus:bg-[var(--color-primary-w90)] focus:text-[var(--color-primary-text-w10)]"
                        onSelect={e => e.preventDefault()}
                    >
                        <Settings className="mr-2 h-4 w-4" />
                        <span>Settings</span>
                    </DropdownMenuItem>
                </DialogTrigger>
            )}
            <DialogContent className="max-h-[90vh] w-[90vw] !max-w-[1200px] gap-0 p-0" showCloseButton={true}>
                <VisuallyHidden>
                    <DialogTitle>Settings</DialogTitle>
                    <DialogDescription>Configure application settings</DialogDescription>
                </VisuallyHidden>
                <div className="flex h-[80vh] overflow-hidden">
                    {/* Sidebar */}
                    <div className="bg-muted/30 flex w-64 flex-col border-r p-4">
                        <div className="mb-6 flex items-center justify-between px-2">
                            <h2 className="text-lg font-semibold">Settings</h2>
                        </div>

                        <nav className="flex-1 space-y-1">
                            <SidebarItem icon={<Type className="size-4" />} label="General" value="general" active={activeSection === "general"} onClick={() => setActiveSection("general")} />
                            {speechEnabled && <SidebarItem icon={<Volume2 className="size-4" />} label="Speech" value="speech" active={activeSection === "speech"} onClick={() => setActiveSection("speech")} />}
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
