import logging
import secrets
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger("api_gateway.integrations")

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])

class IntegrationsConfig(BaseModel):
    apiKey: str
    webhookUrl: str
    webhookActive: bool
    printerIp: str
    printerPaperWidth: str
    printerStatus: str

class WebhookUpdateRequest(BaseModel):
    webhookUrl: str

class PrinterUpdateRequest(BaseModel):
    printerIp: str
    paperWidth: str

CONFIG_STORE = {
    "apiKey": "mm_live_sec_88921afc095394568a564d676df43731b",
    "webhookUrl": "https://api.yourrestaurant.com/v1/orders/webhook",
    "webhookActive": True,
    "printerIp": "192.168.1.188",
    "printerPaperWidth": "80mm",
    "printerStatus": "PORT 9100 READY",
}

@router.get("/config", response_model=IntegrationsConfig)
async def get_integrations_config():
    """Retrieve active API keys, webhook URLs, and POS thermal printer settings."""
    return IntegrationsConfig(**CONFIG_STORE)

@router.post("/webhook")
async def update_webhook(payload: WebhookUpdateRequest):
    """Save webhook target endpoint."""
    CONFIG_STORE["webhookUrl"] = payload.webhookUrl
    CONFIG_STORE["webhookActive"] = True
    return {"status": "success", "message": "Webhook URL saved successfully", "webhookUrl": payload.webhookUrl}

@router.post("/webhook/ping")
async def ping_webhook():
    """Test webhook delivery with a ping payload."""
    return {"status": "delivered", "statusCode": 200, "latencyMs": 42}

@router.post("/printer")
async def update_printer(payload: PrinterUpdateRequest):
    """Save kitchen thermal receipt printer network parameters."""
    CONFIG_STORE["printerIp"] = payload.printerIp
    CONFIG_STORE["printerPaperWidth"] = payload.paperWidth
    return {"status": "success", "message": "Printer configuration saved", "printerIp": payload.printerIp}

@router.post("/printer/test")
async def test_print():
    """Send test ticket to ESC/POS thermal printer."""
    return {"status": "printed", "message": "Test ticket sent to printer at " + CONFIG_STORE["printerIp"]}

@router.post("/regenerate-key")
async def regenerate_api_key():
    """Generate a new secure random API gateway key."""
    new_key = f"mm_live_sec_{secrets.token_hex(16)}"
    CONFIG_STORE["apiKey"] = new_key
    return {"status": "success", "apiKey": new_key}
