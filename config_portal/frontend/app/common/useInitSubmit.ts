import { useState } from "react";
import { submitInitConfig } from "./submitConfig";

type UpdateData = (newData: Partial<Record<string, unknown>>) => void;

export function useInitSubmit(
  data: Partial<Record<string, unknown>>,
  updateData: UpdateData
) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const submit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    const { error } = await submitInitConfig(data as Record<string, unknown>);
    if (error) {
      setSubmitError(error);
      setIsSubmitting(false);
      return;
    }
    updateData({ showSuccess: true });
    setIsSubmitting(false);
  };

  const clearError = () => setSubmitError(null);

  return { isSubmitting, submitError, submit, clearError };
}
