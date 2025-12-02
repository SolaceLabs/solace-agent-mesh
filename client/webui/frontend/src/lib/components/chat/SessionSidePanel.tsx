import React, { useState, useEffect, useMemo } from "react";

import { PanelLeftIcon, PanelRightIcon, Edit, Bot, FolderOpen, NotepadText, MessageCircle, Tag, FileBox, Workflow, HelpCircle, Library, User } from "lucide-react";

import {
    Button,
    Accordion,
    AccordionItem,
    AccordionTrigger,
    AccordionContent,
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/lib/components/ui";
import { useChatContext, useConfigContext } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";
import { SessionSearch } from "@/lib/components/chat/SessionSearch";
import { cn } from "@/lib/utils";

import { ChatSessions } from "./ChatSessions";
import { SessionList } from "./SessionList";

interface NavItem {
    id: string;
    label: string;
    icon: React.ElementType;
    onClick?: () => void;
    badge?: string;
}

// Navigation item button component
const NavItemButton: React.FC<{
    item: NavItem;
    isActive: boolean;
    onClick: () => void;
    className?: string;
}> = ({ item, isActive, onClick, className }) => (
    <Button variant={isActive ? "secondary" : "ghost"} onClick={onClick} className={cn("h-9 w-full justify-start px-2 text-sm font-normal", isActive && "bg-accent", className)}>
        <item.icon className="mr-2 size-4" />
        {item.label}
        {item.badge && <span className="ml-auto rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-600">{item.badge}</span>}
    </Button>
);

interface SessionSidePanelProps {
    onToggle: () => void;
    currentPage?: "chat" | "agentMesh" | "projects" | "prompts";
    isCollapsed?: boolean;
    onNavigate?: (page: string) => void;
}

export const SessionSidePanel: React.FC<SessionSidePanelProps> = ({ onToggle, currentPage = "chat", isCollapsed = false, onNavigate }) => {
    const [activeItem, setActiveItem] = useState<string>("chats");
    const [expandedAccordions, setExpandedAccordions] = useState<string[]>(["recent-chats"]);
    const [showAllChats, setShowAllChats] = useState(false);
    const [selectedProject, setSelectedProject] = useState<string>("all");
    const { handleNewSession, handleSwitchSession } = useChatContext();
    const { configFeatureEnablement, persistenceEnabled } = useConfigContext();
    const { projects } = useProjectContext();

    // Feature flags
    const projectsEnabled = configFeatureEnablement?.projects ?? false;
    const promptLibraryEnabled = configFeatureEnablement?.promptLibrary ?? false;

    // Update active item when current page changes
    useEffect(() => {
        if (currentPage === "agentMesh") {
            setActiveItem("agents");
        } else if (currentPage === "projects") {
            setActiveItem("projects");
        } else if (currentPage === "prompts") {
            setActiveItem("prompts");
        } else {
            setActiveItem("chats");
        }
    }, [currentPage]);

    const handleItemClick = (itemId: string, item: NavItem) => {
        setActiveItem(itemId);

        if (item.onClick) {
            item.onClick();
            return;
        }

        // Handle navigation based on item id
        switch (itemId) {
            case "agents":
                onNavigate?.("agentMesh");
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("navigate-to-agents", {
                            detail: { keepSessionPanel: true },
                        })
                    );
                }
                break;
            case "chats":
                onNavigate?.("chat");
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("navigate-to-chat"));
                }
                break;
            case "projects":
                onNavigate?.("projects");
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("navigate-to-projects"));
                }
                break;
            case "prompts":
                onNavigate?.("prompts");
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("navigate-to-prompts"));
                }
                break;
        }
    };

    const handleNewChatClick = () => {
        // Switch to chat view first, then directly start new session
        if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("navigate-to-chat"));
        }
        handleNewSession();
    };

    // Get unique project names from projects list
    const projectNames = useMemo(() => {
        return projects.map(p => p.name).sort((a, b) => a.localeCompare(b));
    }, [projects]);

    // Get the project ID for the selected project name (for search filtering)
    const selectedProjectId = useMemo(() => {
        if (selectedProject === "all") return null;
        const project = projects.find(p => p.name === selectedProject);
        return project?.id || null;
    }, [selectedProject, projects]);

    // Define navigation items
    const recentChatsItems: NavItem[] = [{ id: "labels", label: "Labels", icon: Tag }];

    const libraryItems: NavItem[] = [{ id: "artifacts", label: "Artifacts", icon: FileBox }];

    if (projectsEnabled) {
        libraryItems.push({ id: "projects", label: "Projects", icon: FolderOpen });
    }

    if (promptLibraryEnabled) {
        libraryItems.push({ id: "prompts", label: "Prompts", icon: NotepadText });
    }

    const agentsItems: NavItem[] = [
        { id: "agents", label: "Agent Mesh", icon: Bot },
        { id: "agent-workflows", label: "Agent Workflows", icon: Workflow },
    ];

    const userAccountItems: NavItem[] = [{ id: "help", label: "Help & Documentation", icon: HelpCircle }];

    return (
        <div className={`session-side-panel bg-background flex h-full flex-col border-r transition-all duration-300 ${isCollapsed ? "w-16" : "w-80"}`}>
            {isCollapsed ? (
                /* Collapsed View - Icon Only (matches expanded view order) */
                <>
                    {/* Icon Stack */}
                    <div className="flex flex-col items-center gap-2 py-3">
                        <Button variant="ghost" onClick={onToggle} className="h-10 w-10 p-2" tooltip="Expand Sessions Panel">
                            <PanelRightIcon className="size-5" />
                        </Button>

                        {/* Divider */}
                        <div className="border-border my-1 w-8 border-t" />

                        {/* New Chat */}
                        <Button variant="default" onClick={handleNewChatClick} className="h-10 w-10 p-2" tooltip="New Chat">
                            <Edit className="size-5" />
                        </Button>

                        {/* Divider */}
                        <div className="border-border my-1 w-8 border-t" />

                        {/* Library Icons */}
                        <Button variant={activeItem === "artifacts" ? "default" : "ghost"} onClick={() => handleItemClick("artifacts", { id: "artifacts", label: "Artifacts", icon: FileBox })} className="h-10 w-10 p-2" tooltip="Artifacts">
                            <FileBox className="size-5" />
                        </Button>
                        {projectsEnabled && (
                            <Button variant={activeItem === "projects" ? "default" : "ghost"} onClick={() => handleItemClick("projects", { id: "projects", label: "Projects", icon: FolderOpen })} className="h-10 w-10 p-2" tooltip="Projects">
                                <FolderOpen className="size-5" />
                            </Button>
                        )}
                        {promptLibraryEnabled && (
                            <Button variant={activeItem === "prompts" ? "default" : "ghost"} onClick={() => handleItemClick("prompts", { id: "prompts", label: "Prompts", icon: NotepadText })} className="h-10 w-10 p-2" tooltip="Prompts">
                                <NotepadText className="size-5" />
                            </Button>
                        )}

                        {/* Divider */}
                        <div className="border-border my-1 w-8 border-t" />

                        {/* Agents Icons */}
                        <Button variant={activeItem === "agents" ? "default" : "ghost"} onClick={() => handleItemClick("agents", { id: "agents", label: "Agents", icon: Bot })} className="h-10 w-10 p-2" tooltip="Agents">
                            <Bot className="size-5" />
                        </Button>

                        {/* Divider */}
                        <div className="border-border my-1 w-8 border-t" />

                        {/* Recent Chats */}
                        <Button variant={activeItem === "chats" ? "default" : "ghost"} onClick={() => handleItemClick("chats", { id: "chats", label: "Chats", icon: MessageCircle })} className="h-10 w-10 p-2" tooltip="Recent Chats">
                            <MessageCircle className="size-5" />
                        </Button>
                    </div>

                    {/* Account/Settings at bottom */}
                    <div className="mt-auto flex flex-col items-center gap-2 border-t p-2">
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-10 w-10 p-2" tooltip="Account">
                                    <User className="size-5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="center" side="right" className="w-56">
                                {userAccountItems.map(item => (
                                    <DropdownMenuItem key={item.id} onClick={() => handleItemClick(item.id, item)} className="cursor-pointer">
                                        <item.icon className="mr-2 size-4" />
                                        {item.label}
                                    </DropdownMenuItem>
                                ))}
                                <DropdownMenuSeparator />
                                {/* Settings Dialog trigger */}
                                <SettingsDialog variant="nav-item" />
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </>
            ) : (
                /* Expanded View with Accordions */
                <>
                    {/* Header with Solace Icon and Collapse Button */}
                    <div className="flex items-center justify-between border-b px-4 py-2">
                        <SolaceIcon className="h-12 w-12" />
                        <Button variant="ghost" onClick={onToggle} className="h-10 w-10 p-2" tooltip="Collapse Sessions Panel">
                            <PanelLeftIcon className="size-5" />
                        </Button>
                    </div>

                    {/* Scrollable Navigation Section with Accordions */}
                    <div className="flex-1 overflow-y-auto px-2 py-2">
                        {/* New Chat Button - Top Level */}
                        <Button variant="default" onClick={handleNewChatClick} className="mb-2 h-10 w-full justify-start text-sm font-medium">
                            <Edit className="mr-2 size-4" />
                            New Chat
                        </Button>

                        <Accordion type="multiple" value={expandedAccordions} onValueChange={setExpandedAccordions} className="w-full space-y-1">
                            {/* Library Accordion */}
                            {libraryItems.length > 0 && (
                                <AccordionItem value="library" className="rounded-lg border !border-b">
                                    <AccordionTrigger className="hover:bg-accent/50 rounded-t-lg px-3 py-2 text-sm font-medium hover:no-underline">
                                        <span className="flex items-center gap-2">
                                            <Library className="size-4" />
                                            Library
                                        </span>
                                    </AccordionTrigger>
                                    <AccordionContent className="px-1 pb-2">
                                        <div className="flex flex-col gap-0.5">
                                            {libraryItems.map(item => (
                                                <NavItemButton key={item.id} item={item} isActive={activeItem === item.id} onClick={() => handleItemClick(item.id, item)} />
                                            ))}
                                        </div>
                                    </AccordionContent>
                                </AccordionItem>
                            )}

                            {/* Agents Accordion */}
                            <AccordionItem value="agents" className="rounded-lg border !border-b">
                                <AccordionTrigger className="hover:bg-accent/50 rounded-t-lg px-3 py-2 text-sm font-medium hover:no-underline">
                                    <span className="flex items-center gap-2">
                                        <Bot className="size-4" />
                                        Agents
                                    </span>
                                </AccordionTrigger>
                                <AccordionContent className="px-1 pb-2">
                                    <div className="flex flex-col gap-0.5">
                                        {agentsItems.map(item => (
                                            <NavItemButton key={item.id} item={item} isActive={activeItem === item.id} onClick={() => handleItemClick(item.id, item)} />
                                        ))}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>

                            {/* Recent Chats Accordion */}
                            <AccordionItem value="recent-chats" className="rounded-lg border !border-b">
                                <AccordionTrigger className="hover:bg-accent/50 rounded-t-lg px-3 py-2 text-sm font-medium hover:no-underline">
                                    <span className="flex items-center gap-2">
                                        <MessageCircle className="size-4" />
                                        Recent Chats
                                    </span>
                                </AccordionTrigger>
                                <AccordionContent className="pt-1 pb-2">
                                    {/* Project Filter - Always show when persistence is enabled */}
                                    {persistenceEnabled && (
                                        <div className="mb-2 flex items-center gap-2 px-2">
                                            <label className="text-xs font-medium whitespace-nowrap">Project:</label>
                                            <Select value={selectedProject} onValueChange={setSelectedProject}>
                                                <SelectTrigger className="h-8 flex-1 text-xs">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="all">All Chats</SelectItem>
                                                    {projectNames.length > 0 &&
                                                        projectNames.map(projectName => (
                                                            <SelectItem key={projectName} value={projectName}>
                                                                {projectName}
                                                            </SelectItem>
                                                        ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    )}

                                    {/* Labels */}
                                    <div className="mb-2 flex flex-col gap-0.5 px-1">
                                        {recentChatsItems.map(item => (
                                            <NavItemButton key={item.id} item={item} isActive={activeItem === item.id} onClick={() => handleItemClick(item.id, item)} />
                                        ))}
                                    </div>

                                    {/* Search Bar */}
                                    <div className="mb-2 px-2">
                                        <SessionSearch onSessionSelect={handleSwitchSession} projectId={selectedProjectId} />
                                    </div>
                                    {/* Chat Sessions List */}
                                    <div className={`px-2 ${showAllChats ? "max-h-[400px] overflow-y-auto" : ""}`}>
                                        {showAllChats ? <SessionList projects={projects} /> : <ChatSessions compact={true} maxItems={5} onShowAll={() => setShowAllChats(true)} projectFilter={selectedProject} />}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>
                        </Accordion>
                    </div>

                    {/* Sticky User Account Section at Bottom - Dropdown Menu */}
                    <div className="bg-background border-t px-2 py-2">
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-10 w-full justify-start text-sm font-medium">
                                    <User className="mr-2 size-4" />
                                    Account
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="start" side="top" className="w-56">
                                {userAccountItems.map(item => (
                                    <DropdownMenuItem key={item.id} onClick={() => handleItemClick(item.id, item)} className="cursor-pointer">
                                        <item.icon className="mr-2 size-4" />
                                        {item.label}
                                    </DropdownMenuItem>
                                ))}
                                <DropdownMenuSeparator />
                                {/* Settings Dialog trigger */}
                                <SettingsDialog variant="nav-item" />
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </>
            )}
        </div>
    );
};
