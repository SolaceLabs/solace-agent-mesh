import { Loader2 } from "lucide-react";

interface LoadingBlockerProps {
    isLoading: boolean;
    message?: string;
}

export const LoadingBlocker: React.FC<LoadingBlockerProps> = ({ isLoading, message }) => {
    if (!isLoading) {
        return null;
    }

    return (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/50">
            <Loader2 className="size-8 animate-spin text-[var(--color-brand-wMain)]" />
            {message && <p className="text-muted-foreground mt-4 text-sm">{message}</p>}
        </div>
    );
};
