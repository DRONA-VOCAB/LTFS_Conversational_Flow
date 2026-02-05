# Let's Encrypt SSL Setup Guide

This guide explains how to set up Let's Encrypt SSL certificates using the organized approach with certificates stored in the `certs/` directory.

## Quick Setup

1. **Clean up old certificates** (optional):
   ```bash
   ./cleanup_old_certs.sh
   ```

2. **Obtain Let's Encrypt certificate**:
   ```bash
   ./setup_letsencrypt.sh
   ```
   
   **Important:** Port 80 must be free for certbot verification.

3. **Deploy application**:
   ```bash
   ./deploy.sh
   ```

## Detailed Steps

### Prerequisites

- Domain `server2.vo-cab.dev` must point to this server's IP address
- Port 80 must be available (for initial certificate verification)
- `certbot` must be installed (already installed: `certbot 2.9.0`)

### Certificate Setup

The `setup_letsencrypt.sh` script will:

1. Check if certbot is installed (install if needed)
2. Obtain certificate using standalone mode:
   ```bash
   sudo certbot certonly \
     --standalone \
     -d server2.vo-cab.dev \
     --email kashyap.s@vocab-ai.com \
     --agree-tos \
     --no-eff-email
   ```

3. Copy certificates to project `certs/` directory:
   ```bash
   sudo cp /etc/letsencrypt/live/server2.vo-cab.dev/fullchain.pem certs/
   sudo cp /etc/letsencrypt/live/server2.vo-cab.dev/privkey.pem certs/
   ```

4. Set proper permissions:
   ```bash
   sudo chmod 644 certs/fullchain.pem
   sudo chmod 600 certs/privkey.pem
   ```

5. Set up automatic renewal hook

### Certificate Locations

- **Let's Encrypt (source):** `/etc/letsencrypt/live/server2.vo-cab.dev/`
- **Project (used by app):** `./certs/` directory

The deploy script automatically uses certificates from the `certs/` directory.

### Certificate Renewal

Let's Encrypt certificates expire every 90 days. They will auto-renew automatically.

**Test renewal:**
```bash
sudo certbot renew --dry-run
```

**Manual renewal:**
```bash
sudo certbot renew
```

After renewal, the renewal hook automatically copies certificates to `certs/` and reloads the application.

### Troubleshooting

**Certificate not found:**
- Check DNS: `dig server2.vo-cab.dev`
- Verify certificate exists: `ls -la /etc/letsencrypt/live/server2.vo-cab.dev/`
- Check project certs: `ls -la certs/`

**Port 80 in use:**
- Stop any service using port 80 temporarily
- Or use a different method (DNS challenge)

**Permission errors:**
- Certificates in `certs/` should be owned by your user
- Check: `ls -la certs/`
- Fix: `chmod 644 certs/fullchain.pem && chmod 600 certs/privkey.pem`

**Certificate expired:**
- Renew: `sudo certbot renew`
- Redeploy: `./deploy.sh`

## Architecture

```
/etc/letsencrypt/live/server2.vo-cab.dev/  (Let's Encrypt source)
    ↓ (copied by setup script)
./certs/                                    (Project directory)
    ↓ (used by deploy.sh)
FastAPI Application                          (Uses certs from ./certs/)
```

This organized approach keeps certificates in the project directory, making deployment and management easier.

