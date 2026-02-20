import { LifecycleBadge } from "@/lib/components/ui";

export interface NavItemProps {
    id: string;
    label: string;
    isActive: boolean;
    onClick: () => void;
    badge?: string;
}

export const NavItem = ({ label, isActive, onClick, badge }: NavItemProps) => (
    <button role="tab" aria-selected={isActive} onClick={onClick} className={`relative cursor-pointer px-4 py-3 font-medium ${isActive ? "border-b-2 border-(--color-brand-wMain) font-semibold" : ""}`}>
        <span className="flex items-center gap-2">
            {label}
            {badge && <LifecycleBadge variant="transparent">{badge}</LifecycleBadge>}
        </span>
        {isActive && <div className="absolute right-0 bottom-0 left-0 h-0.5" />}
    </button>
);
