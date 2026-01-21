import os
import uvicorn

print("=== TRADING REFINERY BACKEND STARTING ===", flush=True)
print(f"PORT: {os.environ.get('PORT', 'not set')}", flush=True)

port = int(os.environ.get("PORT", 8000))
uvicorn.run("main:app", host="0.0.0.0", port=port)
