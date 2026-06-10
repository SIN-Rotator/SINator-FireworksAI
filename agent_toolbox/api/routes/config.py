"""GMX + Fireworks credentials config CRUD routes.

Docs: config.doc.md
"""
from fastapi import APIRouter
from pydantic import BaseModel
from agent_toolbox.core.config_manager import get_config

router = APIRouter(prefix="/config", tags=["config"])

class ConfigIn(BaseModel):
    gmx_email: str
    gmx_password: str
    fireworks_password: str

class ConfigOut(BaseModel):
    gmx_email: str
    gmx_password: str
    fireworks_password: str

@router.get("", response_model=ConfigOut)
async def get_config_route():
    cfg = get_config()
    return ConfigOut(gmx_email=cfg.gmx_email, gmx_password=cfg.gmx_password, fireworks_password=cfg.fireworks_password)

@router.post("", response_model=ConfigOut)
async def save_config_route(inp: ConfigIn):
    cfg = get_config()
    cfg.save(inp.gmx_email, inp.gmx_password, inp.fireworks_password)
    return ConfigOut(gmx_email=cfg.gmx_email, fireworks_password=cfg.fireworks_password)