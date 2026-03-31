import type { NavItemConfig } from "@/lib/types/fe";

/**
 * Internal type extension for navigation items with submenu tracking
 */
export type NavItem = NavItemConfig & { hasSubmenu?: boolean };
