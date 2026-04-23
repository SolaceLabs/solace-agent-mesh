const cleanDataBeforeSubmit = (data: Record<string, unknown>) => {
  const cleaned = { ...data };
  if (cleaned.namespace && !String(cleaned.namespace).endsWith("/")) {
    cleaned.namespace += "/";
  }
  if (cleaned.container_started) {
    delete cleaned.container_started;
  }
  if (cleaned.broker_type === "container") {
    cleaned.broker_type = "solace";
  }
  return cleaned;
};

export async function submitInitConfig(
  data: Record<string, unknown>
): Promise<{ error: string | null }> {
  const cleaned = cleanDataBeforeSubmit(data);
  try {
    const response = await fetch("api/save_config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...cleaned, force: true }),
    });

    const result = await response.json();

    if (!response.ok) {
      return {
        error: `HTTP error ${response.status}: ${result.message ?? "Unknown error"}`,
      };
    }

    if (result.status !== "success") {
      return { error: result.message ?? "Failed to save configuration" };
    }

    try {
      await fetch("api/shutdown", { method: "POST" });
    } catch (shutdownError) {
      console.error("Error sending shutdown request:", shutdownError);
    }

    return { error: null };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "An unknown error occurred",
    };
  }
}
