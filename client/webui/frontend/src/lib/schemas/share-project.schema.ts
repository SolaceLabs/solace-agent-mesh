import { z } from "zod";

const viewerEntrySchema = z.object({
    id: z.string(),
    email: z.string().nullable(),
});

export const shareProjectFormSchema = z.object({
    viewers: z.array(viewerEntrySchema).superRefine((viewers, ctx) => {
        viewers.forEach((viewer, index) => {
            if (viewer.email === null) {
                ctx.addIssue({
                    code: "custom",
                    message: "Required. Enter an email.",
                    path: [index, "email"],
                });
            }
        });
    }),
    pendingRemoves: z.array(z.string()),
});

export type ShareProjectFormData = z.infer<typeof shareProjectFormSchema>;
export type ViewerEntry = z.infer<typeof viewerEntrySchema>;
