# MotorGuard — Security Threat Checklist & Hardening Guide

## 1. Threat Matrix & Mitigation Checklist

| Threat Vector | Severity | Attack Description | Mitigation Implemented |
| :--- | :---: | :--- | :--- |
| **Exposed Database** | **CRITICAL** | MongoDB exposed on `0.0.0.0:27017` without authentication, allowing unauthorized reads/wipes. | MongoDB binds strictly to internal Docker bridge (`127.0.0.1` locally); root authentication enforced; never mapped to WAN. |
| **MQTT Credential Sniffing** | **HIGH** | Plaintext MQTT (1883) intercepted across local Wi-Fi, revealing sensor readings or injection commands. | Production requires MQTTS (TLS 1.3 on 8883); individual revocable username/passwords per ESP32. |
| **Device Impersonation** | **HIGH** | Malicious device publishes falsified telemetry for another motor's `motor_id`. | Backend cross-verifies authenticated MQTT `client_id`/`username` against the registered `device_id` and assigned `motor_id`. |
| **Hardcoded Secrets in Git** | **HIGH** | Committing Wi-Fi passwords, JWT keys, or database credentials to GitHub. | `.gitignore` excludes all `.env` files; pre-commit git secret scans; placeholders provided in `.env.example`. |
| **Client-Side Auth Bypass** | **HIGH** | User bypasses UI controls to issue administrative motor changes or calibrations. | All permissions are enforced server-side using FastAPI dependency injection (`Depends(require_role("Admin"))`). |
| **Denial of Service via MQTT** | **MEDIUM** | Compromised device floods broker with gigabytes of garbage data. | Broker message size limit capped at 16 KB; backend enforces per-device rate limiting (max 5 Hz). |
| **Clock Skew / Replay** | **MEDIUM** | Old recorded packets replayed to spoof healthy conditions during a physical motor breakdown. | Strict timestamp boundaries (-24h to +5m); unique index on `(device_id, event_id)` drops replayed packets. |
| **Unsafe Remote Access** | **CRITICAL** | Unprotected port-forwarding on factory router exposing gateway to public internet botnets. | Remote access restricted to authenticated VPN (WireGuard/Tailscale) or TLS reverse proxy with mutual auth. |

---

## 2. Server-Enforced Role-Based Access Control (RBAC)

All endpoints check user roles via server-side decorators:

```python
# Server-side authorization pattern:
def require_roles(*allowed_roles: str):
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of: {allowed_roles}. Current role: {current_user.role}"
            )
        return current_user
    return role_checker

# Example protected endpoint:
@router.post("/motors/{motor_id}/maintenance")
async def add_maintenance_record(
    motor_id: str,
    record: MaintenanceCreate,
    user: User = Depends(require_roles("Admin", "Technician"))
):
    ...
```

---

## 3. Physical Hardware & Wi-Fi Provisioning

### The Hardcoded Credential Risk
Embedding production Wi-Fi passwords or MQTT passwords in Arduino `.ino` files creates a major security exposure if firmware is decompiled or source code is committed to version control.

### Selected Provisioning Strategy: Protected SoftAP + Captive Portal
For Phase 5 physical deployment:
1. **First Boot / Reset**: If the ESP32 cannot connect to known Wi-Fi, it enters Provisioning Mode.
2. **Access Point**: It starts a temporary WPA2-protected Wi-Fi access point:
   - SSID: `MotoGuard-Setup-XXXX` (using device MAC address suffix)
   - WPA2 Password: Printed on a physical QR code / serial sticker on the device enclosure.
3. **Captive Portal**: The technician connects with a smartphone/laptop, opens `192.168.4.1`, selects the plant Wi-Fi network, enters the network key, and enters the device MQTT token.
4. **Encrypted NVRAM Storage**: Credentials are saved to the ESP32's non-volatile storage (NVS) using ESP-IDF encrypted NVS partition.
5. **Reboot**: The device reboots and connects directly to the production plant network as an unprivileged client.
