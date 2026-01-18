from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import httpx
from datetime import datetime
from typing import Optional
import asyncio

app = FastAPI(title="Paragraph Upload Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
paragraphs: list[dict] = []
webhook_urls: list[str] = []


class Paragraph(BaseModel):
    content: str


class WebhookConfig(BaseModel):
    url: str


class WebhookPayload(BaseModel):
    event: str
    timestamp: str
    data: dict


@app.get("/")
async def root():
    return {"message": "Paragraph Upload API", "endpoints": ["/paragraphs", "/webhooks"]}


@app.get("/paragraphs")
async def get_paragraphs():
    return {"paragraphs": paragraphs}


@app.post("/paragraphs")
async def upload_paragraph(paragraph: Paragraph):
    new_paragraph = {
        "id": len(paragraphs) + 1,
        "content": paragraph.content,
        "created_at": datetime.now().isoformat()
    }
    paragraphs.append(new_paragraph)

    # Trigger webhooks asynchronously
    asyncio.create_task(notify_webhooks(new_paragraph))

    return {"message": "Paragraph uploaded successfully", "paragraph": new_paragraph}


@app.post("/webhooks")
async def register_webhook(config: WebhookConfig):
    if config.url not in webhook_urls:
        webhook_urls.append(config.url)
    return {"message": "Webhook registered", "url": config.url}


@app.get("/webhooks")
async def list_webhooks():
    return {"webhooks": webhook_urls}


@app.delete("/webhooks")
async def clear_webhooks():
    webhook_urls.clear()
    return {"message": "All webhooks cleared"}


async def notify_webhooks(paragraph: dict):
    payload = {
        "event": "paragraph_uploaded",
        "timestamp": datetime.now().isoformat(),
        "data": paragraph
    }

    async with httpx.AsyncClient() as client:
        for url in webhook_urls:
            try:
                response = await client.post(url, json=payload, timeout=5.0)
                print(f"Webhook sent to {url}: {response.status_code}")
            except Exception as e:
                print(f"Failed to send webhook to {url}: {e}")


# Webhook listener endpoint for demonstration
webhook_received: list[dict] = []


@app.post("/webhook-listener")
async def webhook_listener(payload: dict):
    """Demo endpoint to receive and display webhook notifications"""
    webhook_received.append({
        "received_at": datetime.now().isoformat(),
        "payload": payload
    })
    print(f"🔔 Webhook received: {payload}")
    return {"status": "received"}


@app.get("/webhook-listener")
async def get_received_webhooks():
    """View all received webhook notifications"""
    return {"received_webhooks": webhook_received}


@app.delete("/webhook-listener")
async def clear_received_webhooks():
    webhook_received.clear()
    return {"message": "Received webhooks cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
