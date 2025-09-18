import type { LucideIcon } from "lucide-react";

export interface PluginInterface {
    type: string;
    id: string;
    label: string;
    icon?: LucideIcon;
    priority?: number; // Optional priority for sorting
    render: (data: unknown) => React.ReactNode;
}

export interface PluginManagerInterface {
    plugins: PluginInterface[];
    registerPlugin(plugin: PluginInterface): void;
    getPluginById(id: string): PluginInterface | undefined;
    getPluginsByType(type: string): PluginInterface[];
    renderPlugin(id: string, data: unknown): React.ReactNode | undefined;
}

export * from "./PluginRegistry";
export * from "./constants";
