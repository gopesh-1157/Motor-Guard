# MotorGuard — Production Deployment & Gateway Strategy

## 1. Operational Deployment Philosophy

MotorGuard is engineered from day one for a **Local-First Industrial Gateway** model:
- The entire application stack (FastAPI backend, Mosquitto MQTT broker, MongoDB storage, and Vite static assets) runs on a dedicated always-on edge host (such as an industrial fanless mini-PC, Intel NUC, or Linux server) situated on the factory or workshop local area network.
- **Zero Internet Dependency for Core Monitoring**: All physical ESP32 devices communicate with the local gateway over the local LAN. Sensor sampling, database writes, rule checks, and local dashboard viewing continue unaffected if the facility's external internet connection drops.

---

## 2. Secure Remote Access Architecture

Exposing internal industrial ports (such as MongoDB 27017 or raw MQTT 1883) directly to the public internet via router port-forwarding is strictly prohibited.

```
       [ Remote Authorized User ]
                   |
            (Internet Access)
                   |
                   v
       +-----------------------+
       |   Secure Access Path  |
       | (WireGuard/Tailscale) |
       +-----------+-----------+
                   | Encrypted VPN Tunnel
                   v
       +-----------------------+
       |  Factory Gateway Host |
       |   (192.168.1.100)     |
       |                       |
       |  +-----------------+  |
       |  |  NGINX Reverse  |  |
       |  |  Proxy + TLS    |  |
       |  +--------+--------+  |
       |           |           |
       |           v           |
       |  MotorGuard Services  |
       +-----------------------+
```

### Recommended Remote Paths:
1. **Mesh VPN (Recommended: Tailscale or WireGuard)**:
   - Install the VPN client on the gateway host and the remote engineer's laptop/phone.
   - Remote engineers connect to the gateway's private mesh IP (e.g., `100.x.x.x`).
   - No open router firewall ports required; end-to-end encrypted with modern cryptography.
2. **Authenticated TLS Reverse Proxy (Alternative)**:
   - If browser-only access without a client VPN is required:
   - NGINX or Caddy reverse proxy terminates HTTPS/WSS with a Let's Encrypt certificate.
   - Client access requires HTTP Basic Auth or OAuth2 Single Sign-On proxy before reaching MotorGuard APIs.

---

## 3. Database Persistence, Backup & Recovery

### 3.1 Volume Mount Strategy
All persistent MongoDB data is stored in a dedicated named Docker volume (`mongodb_data`) mapped to a durable physical disk on the gateway host.

### 3.2 Automated Local Backups (`mongodump`)
A daily cron job or Windows Scheduled Task executes a compressed binary backup:
```bash
# Nightly backup script
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec motorguard-mongodb mongodump \
  --db motorguard_db \
  --gzip \
  --archive=/data/backups/motorguard_${TIMESTAMP}.archive.gz
```

### 3.3 Recovery & Disaster Restoration (`mongorestore`)
In the event of gateway hardware failure:
1. Provision replacement gateway host with Docker.
2. Clone repository and copy `.env`.
3. Restore from the most recent archive:
```bash
docker exec -i motorguard-mongodb mongorestore \
  --gzip \
  --archive < /path/to/backup/motorguard_20261009_020000.archive.gz
```

---

## 4. Gateway Hardware Sizing Guidelines

| Parameter | Recommended Minimum Specification |
| :--- | :--- |
| **CPU** | Intel Celeron J4125 / Core i3 or ARM64 (Raspberry Pi 5 4GB+) |
| **RAM** | 4 GB minimum (8 GB recommended for 20+ motors) |
| **Storage** | 64 GB NVMe / SSD with high write endurance |
| **Networking** | Gigabit Ethernet or industrial 2.4/5GHz Wi-Fi 6 |
| **Power** | Dedicated Uninterruptible Power Supply (UPS) with battery backup |
