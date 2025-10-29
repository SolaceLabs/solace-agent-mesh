import { Button } from "@/lib/components/ui/button";
import { Ellipsis } from "lucide-react";

export const MorePopoverButton = (
    <Button variant="ghost" tooltip="More">
        <Ellipsis className="h-5 w-5" />
    </Button>
);
