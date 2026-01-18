from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/webhook-listener")
async def alive():
    return {"status": "listening"}

@app.post("/webhook-listener")
async def webhook(request: Request):
    body = await request.body()
    headers = dict(request.headers)

    print("\n--- WEBHOOK RECEIVED ---")
    print("Headers:", headers)
    print("Raw body:", body.decode("utf-8", errors="replace"))

    try:
        json_body = await request.json()
        print("Parsed JSON:", json_body)
    except Exception as e:
        print("JSON parse failed:", e)

    print("------------------------\n")

    return JSONResponse({"ok": True}, status_code=200)