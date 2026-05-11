import { useMutation } from "@tanstack/react-query";
import { scheduledTaskService } from "@/lib/api/scheduled-tasks";
import type { ConflictValidationRequest, ConflictValidationResult } from "@/lib/api/scheduled-tasks";

// Mutation hook wrapping scheduledTaskService.validateTaskConflict so callers
// can use mutateAsync/isPending instead of calling the service directly and
// managing their own loading flag.
export function useValidateTaskConflict() {
    return useMutation<ConflictValidationResult, Error, ConflictValidationRequest>({
        mutationFn: input => scheduledTaskService.validateTaskConflict(input),
    });
}
