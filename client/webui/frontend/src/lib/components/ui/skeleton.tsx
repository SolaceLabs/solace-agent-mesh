import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
    return <div data-slot="skeleton" className={cn("animate-pulse rounded-md bg-(--secondary-w40)", className)} {...props} />;
}

export { Skeleton };
