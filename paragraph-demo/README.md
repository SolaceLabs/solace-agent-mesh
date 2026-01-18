# Paragraph Upload Demo

A minimal demo showing paragraph uploads with webhook notifications using FastAPI + React.

## Quick Start

### Backend (Terminal 1)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Backend runs at http://localhost:8001

### Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

## How It Works

1. Register a webhook URL (default points to the built-in demo listener)
2. Upload a paragraph
3. The webhook notification appears in the "Received Webhook Notifications" section

## API Endpoints

- `POST /paragraphs` - Upload a paragraph
- `GET /paragraphs` - List all paragraphs
- `POST /webhooks` - Register a webhook URL
- `GET /webhooks` - List registered webhooks
- `POST /webhook-listener` - Demo endpoint to receive webhooks
- `GET /webhook-listener` - View received webhook notifications
