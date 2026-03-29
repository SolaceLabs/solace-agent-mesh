import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { modelKeys } from "@/lib/api/models";

export const InvalidateModelCacheDecorator = (Story: React.ComponentType) => {
    const queryClient = useQueryClient();

    React.useLayoutEffect(() => {
        queryClient.removeQueries({ queryKey: modelKeys.lists() });
    }, [queryClient]);

    return <Story />;
};
