# File: `schemas.py`

Pydantic request/response models for all SINator FastAPI endpoints. Organised into GMX, Fireworks, Pool, and Rotation schema groups.

## Dependencies

- **Imported by:** `agent_toolbox/api/routes/gmx.py`, `agent_toolbox/api/routes/fireworks.py`, `agent_toolbox/api/routes/pool.py`, `agent_toolbox/api/routes/rotation.py`
- **Imports:** `pydantic.BaseModel`, `pydantic.Field`

## Key Classes

| Symbol | Purpose |
|--------|---------|
| `GmxSessionCheckRequest/Response` | GMX session check input/output |
| `GmxAliasRequest/Response` | GMX alias creation |
| `GmxAliasRotateRequest/Response` | Atomic delete+create alias rotation |
| `GmxOtpRequest/Response` | OTP email reading from GMX inbox |
| `GmxInboxOpenResponse` | Inbox navigation result |
| `GmxEmailAddressesResponse` | Email addresses page state |
| `FireworksRegisterRequest/Response` | Fireworks signup |
| `FireworksApiKeyRequest/Response` | API key generation |
| `PoolStatsResponse` | Full pool statistics with per-key details |
| `PoolAddKeyRequest/Response` | Manual key addition |
| `RotationRequest/Response` | Complete GMX→Fireworks→API key rotation flow |

## Important Config/Limits

- Timeout fields constrained: `ge=1000, le=60000` (session check), `ge=5000, le=120000` (alias)
- OTP retries: `ge=1, le=30` (default 12)
- All responses include `execution_time: str` for observability
- `PoolStatsResponse.keys` returns list without secret api_key values
