import { ModelWarningBanner } from "@/lib/components/models/ModelWarningBanner";
import { cn } from "@/lib/utils";

interface PageLayoutProps {
    children: React.ReactNode;
    className?: string;
}

export function PageLayout({ children, className }: PageLayoutProps) {
    return (
        <div className={cn("flex h-full w-full flex-col overflow-hidden", className)}>
            <ModelWarningBanner />
            {children}
        </div>
    );
}
