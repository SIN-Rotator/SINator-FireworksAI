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
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
#  BROWSER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class BrowserStartRequest(BaseModel):
    """Request für Browser-Start."""
    profile_name: str = Field(default="Profile 901", description="Chrome Profil-Name")
    cdp_port: int = Field(default=9222, ge=1024, le=65535, description="CDP Debug-Port")
    headless: bool = Field(default=False, description="Headless-Modus")
    chrome_path: Optional[str] = Field(default=None, description="Pfad zur Chrome Binary")


class BrowserStartResponse(BaseModel):
    """Response für Browser-Start."""
    status: str = Field(..., description="success | already_running | error")
    browser_info: Dict[str, Any] = Field(default_factory=dict, description="Browser-Informationen")
    temp_profile_dir: Optional[str] = Field(default=None, description="Pfad zum Temp-Profil")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung falls status=error")


class BrowserStopResponse(BaseModel):
    """Response für Browser-Stopp."""
    status: str = Field(..., description="stopped | not_running | error")
    cleanup_info: Optional[str] = Field(default=None, description="Cleanup-Information")
    execution_time: str = Field(..., description="Ausführungszeit")


class BrowserStatusResponse(BaseModel):
    """Response für Browser-Status."""
    is_running: bool = Field(..., description="True wenn Browser aktiv")
    cdp_port: Optional[int] = Field(default=None, description="CDP-Port")
    temp_profile: Optional[str] = Field(default=None, description="Temp-Profil-Pfad")
    page_count: int = Field(default=0, description="Anzahl offener Pages")


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
#  COOKIE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class CookieExtractRequest(BaseModel):
    """Request für Cookie-Extraktion."""
    domain_filter: Optional[str] = Field(default="gmx", description="Domain-Filter (None = alle)")
    save_to_file: bool = Field(default=True, description="Cookies in Datei speichern")
    filename: str = Field(default="gmx-cookies.json", description="Dateiname für gespeicherte Cookies")


class CookieExtractResponse(BaseModel):
    """Response für Cookie-Extraktion."""
    status: str = Field(..., description="success | error")
    cookie_count: int = Field(..., description="Anzahl extrahierter Cookies")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Cookie-Statistiken")
    saved_to: Optional[str] = Field(default=None, description="Pfad zur gespeicherten Datei")
    execution_time: str = Field(..., description="Ausführungszeit")
    error: Optional[str] = Field(default=None, description="Fehlermeldung")


class CookieInjectRequest(BaseModel):
    """Request für Cookie-Injektion."""
    filename: str = Field(default="gmx-cookies.json", description="Dateiname der Cookies")
    verify_session: bool = Field(default=True, description="Session nach Injektion prüfen")


class CookieInjectResponse(BaseModel):
    """Response für Cookie-Injektion."""
    status: str = Field(..., description="success | failed | error")
    injected_count: int = Field(..., description="Anzahl injizierter Cookies")
    session_active: bool = Field(default=False, description="True wenn Session nach Injektion aktiv")
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
    available: int = Field(..., description="Verfügbare Keys (incl. geleast)")
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
