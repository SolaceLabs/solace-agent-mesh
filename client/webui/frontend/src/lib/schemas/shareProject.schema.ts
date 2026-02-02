import { z } from "zod";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const viewerEntrySchema = z.object({
    id: z.string(),
    email: z.string().nullable(),
});

export const createShareProjectFormSchema = (identityServiceType: string | null) =>
    z.object({
        viewers: z.array(viewerEntrySchema).superRefine((viewers, ctx) => {
            viewers.forEach((viewer, index) => {
                if (viewer.email === null) {
                    ctx.addIssue({
                        code: "custom",
                        message: "Required. Enter an email.",
                        path: [index, "email"],
                    });
                } else if (identityServiceType === null && !EMAIL_REGEX.test(viewer.email)) {
                    ctx.addIssue({
                        code: "custom",
                        message: "Please enter a valid email address",
                        path: [index, "email"],
                    });
                }
            });
        }),
        pendingRemoves: z.array(z.string()),
    });

export const shareProjectFormSchema = createShareProjectFormSchema(null);

export type ShareProjectFormData = z.infer<typeof shareProjectFormSchema>;
export type ViewerEntry = z.infer<typeof viewerEntrySchema>;
