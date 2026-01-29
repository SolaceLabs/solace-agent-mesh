import { z } from "zod";

const viewerEntrySchema = z.object({
    id: z.string(),
    email: z.string().nullable(),
});

export const shareProjectFormSchema = z.object({
    viewers: z.array(viewerEntrySchema),
    pendingRemoves: z.array(z.string()),
});

export type ShareProjectFormData = z.infer<typeof shareProjectFormSchema>;
export type ViewerEntry = z.infer<typeof viewerEntrySchema>;
