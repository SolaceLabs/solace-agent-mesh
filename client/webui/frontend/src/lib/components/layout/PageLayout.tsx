import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageLayoutProps {
    children: ReactNode;
    className?: string;
}

export function PageLayout({ children, className }: PageLayoutProps) {
    return <div className={cn("flex min-h-0 w-full flex-1 flex-col overflow-hidden", className)}>{children}</div>;
}
