import React from "react";

import { Grid } from "lucide-react";

import { type PluginInterface, type PluginManagerInterface } from ".";
import { PLUGIN_TYPES } from "./constants";
import { AgentMeshCards } from "../components/agents";

/**
 * Plugin Registry to allow adding UI components to:
 * 1. Agent Mesh Layouts
 */
class PluginRegistry implements PluginManagerInterface {
    private _plugins: Record<string, PluginInterface> = {};

    constructor() {
        this.registerDefaultPlugins();
    }

    get plugins(): PluginInterface[] {
        return Object.values(this._plugins);
    }

    registerPlugin(plugin: PluginInterface): void {
        if (this._plugins[plugin.id]) {
            console.warn(`Plugin with ID ${plugin.id} already exists. Overwriting.`);
        }
        this._plugins[plugin.id] = plugin;
    }

    getPluginById(id: string): PluginInterface | undefined {
        return this._plugins[id];
    }

    getPluginsByType(type: string): PluginInterface[] {
        return Object.values(this._plugins).filter(plugin => plugin.type === type);
    }

    private registerDefaultPlugins(): void {
        // Register the default cards layout plugin
        this.registerPlugin({
            type: PLUGIN_TYPES.LAYOUT,
            id: "cards",
            label: "Cards",
            icon: Grid,
            priority: 100,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            render: (data: any) => {
                return <AgentMeshCards agents={data.agents || []} />;
            },
        });
    }

    renderPlugin(id: string, data: unknown): React.ReactNode | undefined {
        const plugin = this.getPluginById(id);
        if (plugin) {
            return plugin.render(data);
        }
        return undefined;
    }
}

export const pluginRegistry = new PluginRegistry();
