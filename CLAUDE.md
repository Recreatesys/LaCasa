# LCS (La Casa) — Odoo 19 Enterprise Project

## Overview
LCS is an Odoo 19 Enterprise implementation and development project.

## Tech Stack
- **Odoo Version**: 19.0 (Enterprise)
- **Enterprise Source**: https://github.com/Recreatesys/enterprise (branch: 19.0)
- **Community Source**: https://github.com/odoo/odoo (branch: 19.0)
- **Server**: Contabo VPS — `ssh root@62.72.47.0`
- **Domain**: https://lacasa.pintartech.online/
- **Database**: `LaCasa_Odoo19` (PostgreSQL, user: odoo19)
- **GitHub**: https://github.com/Recreatesys/LaCasa (branch: main)

## Server Paths
- Odoo install: `/opt/odoo19/odoo19/`
- Venv: `/opt/odoo19/odoo19-venv/`
- Config: `/etc/odoo19.conf`
- Custom addons: `/opt/odoo19/odoo19/custom-addons/`
- Log: `/var/log/odoo/odoo19.log`
- Service: `systemctl restart odoo19`

## Development Workflow
Use `/march` skill for all Odoo development, deployment, and module work.
Target version is **Odoo 19** — use v19 syntax and patterns.

## Deployment
```bash
# Local → GitHub
git push origin main

# Server: pull + upgrade
ssh root@62.72.47.0
cd /opt/odoo19/odoo19/custom-addons && git pull origin main
sudo -u odoo19 /opt/odoo19/odoo19-venv/bin/python3 /opt/odoo19/odoo19/odoo-bin \
  -c /etc/odoo19.conf -d LaCasa_Odoo19 -u module_name --stop-after-init
systemctl restart odoo19
```

## Known Issues
- Recreatesys/enterprise 19.0 fork: `journal_line_ids` → `line_ids` xpath fix required (see memory)
