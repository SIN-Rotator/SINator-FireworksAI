"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Pydantic Schemas                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Definiert alle Request/Response-Modelle für die FastAPI-Endpunkte.          ║
║  Stellt sicher dass Agenten exakte JSON-Strukturen erhalten.                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Docs: schemas.doc.md
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
#  GMX SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class GmxSessionCheckRequest(BaseModel):
    """Request für GMX Session-Check."""
    navigate_to: str = Field(
        default="navigator.gmx.net/mail",
        description="URL die geladen werden soll"
    )
    timeout: int = Field(default=15000, ge=1000, le=60000, description="Timeout in ms")


class GmxSessionCheckResponse(BaseModel):
    """Response für GMX Session-Check."""
    status: str = Field(..., description="logged_in | not_logged_in | consent_required | error")
    current_url: str = Field(..., description="Aktuelle URL nach Navigation")
    session_active: bool = Field(..., description="True wenn Session gültig")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class GmxAliasRequest(BaseModel):
    """Request für GMX Alias-Erstellung."""
    alias_name: Optional[str] = Field(default=None, description="Alias-Name (ohne @gmx.de). Wenn None, wird generiert.")
    delete_existing: bool = Field(default=True, description="Existierenden Alias löschen")
    timeout: int = Field(default=30000, ge=5000, le=120000, description="Timeout in ms")


class GmxAliasResponse(BaseModel):
    """Response für GMX Alias-Erstellung."""
    status: str = Field(..., description="success | failed | no_session | error")
    alias_email: Optional[str] = Field(default=None, description="Vollständige Alias-Email")
    alias_name: Optional[str] = Field(default=None, description="Generierter Alias-Name")
    steps_completed: List[str] = Field(default_factory=list, description="Erfolgreich abgeschlossene Schritte")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class GmxEmailAddressesResponse(BaseModel):
    """Response für E-Mail-Adressen-Seite."""
    status: str = Field(..., description="success | not_logged_in | error")
    current_url: Optional[str] = Field(default=None, description="Aktuelle URL")
    title: Optional[str] = Field(default=None, description="Seitentitel")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class GmxAliasDeleteResponse(BaseModel):
    """Response für Alias-Löschung."""
    status: str = Field(..., description="success | no_alias | not_logged_in | error")
    deleted: bool = Field(default=False, description="True wenn gelöscht oder nicht vorhanden")
    alias: Optional[str] = Field(default=None, description="Der gelöschte Alias-Email (wenn gefunden)")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class GmxAliasRotateRequest(BaseModel):
    """Request für Alias-Rotation (delete + create in einem Aufruf)."""
    new_alias_name: Optional[str] = Field(default=None, description="Neuer Alias-Name. Wenn None, wird generiert.")


class GmxAliasRotateResponse(BaseModel):
    """Response für Alias-Rotation."""
    status: str = Field(..., description="success | partial | failed | error")
    deleted_alias: Optional[str] = Field(default=None, description="Gelöschte Alias-Email")
    created_alias: Optional[str] = Field(default=None, description="Erstellte Alias-Email")
    created_alias_name: Optional[str] = Field(default=None, description="Verwendeter Alias-Name")
    steps_completed: List[str] = Field(default_factory=list, description="Erfolgreich abgeschlossene Schritte")
    steps_failed: List[str] = Field(default_factory=list, description="Fehlgeschlagene Schritte")
    execution_time: str = Field(..., description="Gesamtausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class GmxInboxOpenResponse(BaseModel):
    """Response für Inbox-Öffnung."""
    status: str = Field(..., description="success | not_logged_in | error")
    current_url: Optional[str] = Field(default=None, description="Aktuelle URL")
    execution_time: str = Field(..., description="Ausführungszeit")


class GmxOtpRequest(BaseModel):
    """Request für GMX OTP-Lesen."""
    sender_filter: str = Field(default="fireworks", description="Absender-Filter für OTP-Email")
    max_retries: int = Field(default=12, ge=1, le=30, description="Maximale Polling-Versuche")
    retry_delay: int = Field(default=5000, ge=1000, le=30000, description="Delay zwischen Versuchen in ms")


class GmxOtpResponse(BaseModel):
    """Response für GMX OTP-Lesen."""
    status: str = Field(..., description="success | not_found | timeout | error")
    otp_url: Optional[str] = Field(default=None, description="Bestätigungs-URL aus der Email")
    email_subject: Optional[str] = Field(default=None, description="Betreff der OTP-Email")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


# ═══════════════════════════════════════════════════════════════════════════════
#  FIREWORKS SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class FireworksRegisterRequest(BaseModel):
    """Request für Fireworks Login."""
    email: str = Field(..., description="GMX Alias-Email")
    password: str = Field(..., description="Passwort für Fireworks Account")
    gmx_password: Optional[str] = Field(default=None, description="GMX Passwort (deprecated)")


class FireworksRegisterResponse(BaseModel):
    """Response für Fireworks Login."""
    status: str = Field(..., description="success | failed | error")
    account_email: str = Field(..., description="Account Email")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class FireworksApiKeyRequest(BaseModel):
    """Request für Fireworks API-Key-Erstellung."""
    key_name: str = Field(default="sinator-key", description="Name für den API-Key")


class FireworksApiKeyResponse(BaseModel):
    """Response für Fireworks API-Key-Erstellung."""
    status: str = Field(..., description="success | failed | error")
    api_key: Optional[str] = Field(default=None, description="Generierter API-Key")
    key_name: str = Field(..., description="Name des Keys")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


# ═══════════════════════════════════════════════════════════════════════════════
#  POOL SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PoolStatsResponse(BaseModel):
    """Response für Pool-Statistiken."""
    status: str = Field(..., description="success | error")
    total: int = Field(..., description="Gesamtanzahl Keys")
    used: int = Field(..., description="Manuell verbrauchte Keys")
    suspended: int = Field(default=0, description="Von Fireworks gesperrte Keys")
    leased: int = Field(default=0, description="Aktuell geleaste Keys (von Proxys belegt)")
    available: int = Field(..., description="Verfügbare Keys (exkl. used, suspended, leased)")
    assigned: int = Field(default=0, description="V19.14: Keys mit sticky assignment")
    shared: int = Field(default=0, description="V19.14: Keys mit mehreren active_consumers")
    keys: List[Dict[str, Any]] = Field(default_factory=list, description="Liste aller Keys (ohne Secret)")
    execution_time: str = Field(..., description="Ausführungszeit")


class PoolAddKeyRequest(BaseModel):
    """Request zum Hinzufügen eines API-Keys."""
    api_key: str = Field(..., description="Fireworks API-Key")
    alias_email: str = Field(..., description="Zugehörige GMX Alias-Email")
    key_name: str = Field(default="sinator-key", description="Name des Keys")


class PoolAddKeyResponse(BaseModel):
    """Response für Key-Hinzufügung."""
    status: str = Field(..., description="success | error")
    key_id: str = Field(..., description="ID des gespeicherten Keys")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


# ═══════════════════════════════════════════════════════════════════════════════
#  ROTATION SCHEMAS (Komplett-Flow)
# ═══════════════════════════════════════════════════════════════════════════════

class RotationRequest(BaseModel):
    """Request für komplette Account-Rotation (GMX Alias + Fireworks Account + API-Key)."""
    new_alias_name: Optional[str] = Field(default=None, description="Neuer GMX Alias-Name. Wenn None, wird generiert.")
    fireworks_password: Optional[str] = Field(default=None, description="Passwort für neuen Fireworks Account (optional — Backend nutzt Config)")
    gmx_alias_name: Optional[str] = Field(default=None, description="GMX Alias-Name für Rotation (alt)")
    save_to_pool: bool = Field(default=True, description="API-Key im Pool speichern")


class RotationResponse(BaseModel):
    """Response für komplette Account-Rotation."""
    status: str = Field(..., description="success | partial | failed | error")
    gmx_alias: Optional[str] = Field(default=None, description="Neue GMX Alias-Email")
    fireworks_account: Optional[str] = Field(default=None, description="Registrierte Fireworks Email")
    api_key: Optional[str] = Field(default=None, description="Generierter Fireworks API-Key")
    api_key_name: Optional[str] = Field(default=None, description="Name des API-Keys")
    steps_completed: List[str] = Field(default_factory=list, description="Erfolgreich abgeschlossene Schritte")
    steps_failed: List[str] = Field(default_factory=list, description="Fehlgeschlagene Schritte")
    execution_time: str = Field(..., description="Gesamtausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


# ═══════════════════════════════════════════════════════════════════════════════
#  V19.14 SOFT-OWNERSHIP SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentKeyRequest(BaseModel):
    """V19.14: Request for soft-ownership key assignment."""
    agent_id: str = Field(..., description="Unique agent identifier")
    preferred_key_id: Optional[str] = Field(default=None, description="Previously assigned key ID (sticky)")


class AgentKeyResponse(BaseModel):
    """V19.14: Response for soft-ownership key assignment."""
    status: str = Field(..., description="success | error")
    api_key: str = Field(..., description="Fireworks API key (hydrated)")
    key_id: str = Field(..., description="Key ID")
    alias_email: str = Field(default="", description="GMX alias email")
    key_name: str = Field(default="", description="Key display name")
    shared: bool = Field(default=False, description="True if key is shared with other agents")
    active_consumers: List[str] = Field(default_factory=list, description="Agent IDs currently using this key")
    assigned_to: Optional[str] = Field(default=None, description="Permanent sticky owner")
    shared_count: int = Field(default=0, description="Total times this key was shared")


class AgentReleaseRequest(BaseModel):
    """V19.14: Request to release an agent's key."""
    agent_id: str = Field(..., description="Agent identifier")
    key_id: str = Field(..., description="Key ID to release")


class AgentReleaseResponse(BaseModel):
    """V19.14: Response for key release."""
    status: str = Field(..., description="success | error")
    released: bool = Field(default=False, description="True if key was released")
    key_id: str = Field(..., description="Released key ID")
