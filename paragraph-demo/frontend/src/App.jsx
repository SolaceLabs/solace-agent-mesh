import { useState, useEffect } from "react";
import newsLogo from "./SAMNEWS.png";

const API_URL = "http://localhost:8001";

function App() {
  const [paragraphText, setParagraphText] = useState("");
  const [paragraphs, setParagraphs] = useState([]);
  const [webhookUrl, setWebhookUrl] = useState(
    "http://localhost:8002/webhook-listener",
  );
  const [webhooks, setWebhooks] = useState([]);
  const [receivedWebhooks, setReceivedWebhooks] = useState([]);
  const [status, setStatus] = useState(null);
  const [showDebug, setShowDebug] = useState(false);

  useEffect(() => {
    fetchParagraphs();
    fetchWebhooks();
    fetchReceivedWebhooks();
  }, []);

  // Auto-refresh received webhooks every 2 seconds
  useEffect(() => {
    const interval = setInterval(fetchReceivedWebhooks, 2000);
    return () => clearInterval(interval);
  }, []);

  const fetchParagraphs = async () => {
    try {
      const res = await fetch(`${API_URL}/paragraphs`);
      const data = await res.json();
      setParagraphs(data.paragraphs);
    } catch (err) {
      console.error("Failed to fetch paragraphs:", err);
    }
  };

  const fetchWebhooks = async () => {
    try {
      const res = await fetch(`${API_URL}/webhooks`);
      const data = await res.json();
      setWebhooks(data.webhooks);
    } catch (err) {
      console.error("Failed to fetch webhooks:", err);
    }
  };

  const fetchReceivedWebhooks = async () => {
    try {
      const res = await fetch(`${API_URL}/webhook-listener`);
      const data = await res.json();
      setReceivedWebhooks(data.received_webhooks);
    } catch (err) {
      console.error("Failed to fetch received webhooks:", err);
    }
  };

  const uploadParagraph = async () => {
    if (!paragraphText.trim()) return;

    try {
      const res = await fetch(`${API_URL}/paragraphs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: paragraphText }),
      });
      const data = await res.json();
      setStatus({ type: "success", message: "Paragraph uploaded!" });
      setParagraphText("");
      fetchParagraphs();
      setTimeout(() => setStatus(null), 3000);
    } catch (err) {
      setStatus({ type: "error", message: "Failed to upload paragraph" });
    }
  };

  const registerWebhook = async () => {
    if (!webhookUrl.trim()) return;

    try {
      await fetch(`${API_URL}/webhooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: webhookUrl }),
      });
      setStatus({ type: "success", message: "Webhook registered!" });
      fetchWebhooks();
      setTimeout(() => setStatus(null), 3000);
    } catch (err) {
      setStatus({ type: "error", message: "Failed to register webhook" });
    }
  };

  const clearReceivedWebhooks = async () => {
    try {
      await fetch(`${API_URL}/webhook-listener`, { method: "DELETE" });
      setReceivedWebhooks([]);
    } catch (err) {
      console.error("Failed to clear webhooks:", err);
    }
  };

  return (
    <div className="container">
      <h1
        style={{ display: "flex", alignItems: "center", marginBottom: "20px" }}
      >
        <img
          src={newsLogo}
          alt="News Channel"
          style={{ marginRight: "15px", height: "100px" }} // Adjust height for better spacing
        />
        SAM NEWS CHANNEL
      </h1>

      {status && (
        <div className={`status ${status.type}`}>{status.message}</div>
      )}

      <div className="section">
        <h2>Add new NEWS Article</h2>
        <textarea
          value={paragraphText}
          onChange={(e) => setParagraphText(e.target.value)}
          placeholder="Enter your news here..."
        />
        <button onClick={uploadParagraph}>Upload Paragraph</button>
      </div>

      <div className="section">
        <h2>Breaking NEWS! ({paragraphs.length})</h2>
        <button className="secondary" onClick={fetchParagraphs}>
          Refresh
        </button>
        {paragraphs.length === 0 ? (
          <p style={{ color: "#888" }}>No paragraphs uploaded yet.</p>
        ) : (
          paragraphs.map((p) => (
            <div key={p.id} className="paragraph-item">
              <p>{p.content}</p>
              <small>
                ID: {p.id} | Created: {new Date(p.created_at).toLocaleString()}
              </small>
            </div>
          ))
        )}
      </div>

      <div className="section">
        <h2>Debug Settings</h2>
        <button onClick={() => setShowDebug(!showDebug)}>
          {showDebug ? "Hide" : "Show"} Debug Settings
        </button>
        {showDebug && (
          <>
            <div className="section">
              <h2>Register Webhook</h2>
              <p style={{ color: "#666", fontSize: "14px" }}>
                Register a URL to receive notifications when paragraphs are
                uploaded.
              </p>
              <div className="flex-row">
                <input
                  type="text"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  placeholder="Webhook URL"
                  style={{ flex: 1 }}
                />
                <button onClick={registerWebhook}>Register</button>
              </div>
              {webhooks.length > 0 && (
                <div style={{ marginTop: "10px" }}>
                  <strong>Registered webhooks:</strong>
                  <ul>
                    {webhooks.map((url, i) => (
                      <li key={i} style={{ fontSize: "14px", color: "#666" }}>
                        {url}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="section">
              <h2>
                Received Webhook Notifications ({receivedWebhooks.length})
              </h2>
              <button className="secondary" onClick={fetchReceivedWebhooks}>
                Refresh
              </button>
              <button className="secondary" onClick={clearReceivedWebhooks}>
                Clear
              </button>
              <p style={{ color: "#666", fontSize: "14px" }}>
                This shows webhooks received by the demo listener endpoint.
              </p>
              {receivedWebhooks.length === 0 ? (
                <p style={{ color: "#888" }}>
                  No webhook notifications received yet.
                </p>
              ) : (
                receivedWebhooks.map((w, i) => (
                  <div key={i} className="webhook-item">
                    <small>
                      Received: {new Date(w.received_at).toLocaleString()}
                    </small>
                    <pre>{JSON.stringify(w.payload, null, 2)}</pre>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
