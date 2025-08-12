import { Spinner } from "@/lib/components/ui/spinner";

// @hidden
export default function MessageLoading({ className = "" }: { className?: string }) {
    return <Spinner size="small" variant="primary" className={className} />;
}
