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
        <div className="overlay-backdrop fixed inset-0 z-50 flex flex-col items-center justify-center">
            <Loader2 className="size-8 animate-spin text-(--brand-wMain)" />
            {message && <p className="mt-4 text-sm text-(--secondary-text-wMain)">{message}</p>}
        </div>
    );
};
