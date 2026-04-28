import { useMutation } from "@tanstack/react-query";

import * as researchService from "./service";

export function useSubmitPlanResponse() {
    return useMutation({
        mutationFn: researchService.submitPlanResponse,
    });
}
