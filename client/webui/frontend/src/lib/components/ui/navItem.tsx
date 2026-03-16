import { LifecycleBadge } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

export interface NavItemProps {
    id: string;
    label: string;
    isActive: boolean;
    onClick: () => void;
    badge?: string;
}

export const NavItem = ({ label, isActive, onClick, badge }: NavItemProps) => (
    <button role="tab" aria-selected={isActive} onClick={onClick} className={cn("h-11 cursor-pointer px-4 font-medium", isActive ? "font-semibold shadow-[inset_0_-2px_0_var(--brand-wMain)]" : "")}>
        <div className="flex h-full items-center gap-2">
            {label}
            {badge && <LifecycleBadge variant="transparent">{badge}</LifecycleBadge>}
        </div>
    </button>
);
