import type { VariantProps } from "class-variance-authority";
import type { buttonVariants } from "@/lib/components/ui/button";

export type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];
