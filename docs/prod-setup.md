# Production Setup

This documents the current production deployment for `drzewo`.

## Architecture

- Single DigitalOcean droplet
- Nginx terminates TLS and proxies to Gunicorn over a Unix socket
- Gunicorn serves Flask app from `/home/drzewo/webapp/drzewo`
- PostgreSQL runs on the same droplet
- Municipal dataset files are downloaded and loaded from a laptop, not on the droplet

This is a single failure domain. The database and app server live on the same machine.

## Paths

- App checkout: `/home/drzewo/webapp/drzewo`
- Gunicorn socket: `/home/drzewo/webapp/drzewo/drzewo.sock`
- Nginx site config: `/etc/nginx/sites-enabled/treeseek.ca`
- Gunicorn systemd unit: `/etc/systemd/system/gunicorn.service`
- Nginx access log: `/var/log/nginx/access.log`
- Nginx error log: `/var/log/nginx/error.log`

Repo snapshots of the live config:

- `/Users/greg/dev/drzewo/ops/systemd/gunicorn.service`
- `/Users/greg/dev/drzewo/ops/nginx/treeseek.ca.conf`
- `/Users/greg/dev/drzewo/ops/nginx/http-rate-limit.conf`

## Deploy

From local repo checkout:

```bash
./deploy.sh
```

This copies app files to the droplet, installs requirements into the existing virtualenv, and restarts Gunicorn.

## Service checks

```bash
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -n 100 --no-pager
sudo nginx -t
sudo systemctl reload nginx
```

## Basic restore checklist

1. Provision Ubuntu droplet
2. Install Nginx, Python, PostgreSQL, and Certbot
3. Create `drzewo` Unix user and app directory `/home/drzewo/webapp/drzewo`
4. Clone repo into app directory
5. Create virtualenv and install requirements
6. Restore `.env`
7. Restore PostgreSQL database from backup
8. Install Gunicorn unit from `ops/systemd/gunicorn.service`
9. Install Nginx site config from `ops/nginx/treeseek.ca.conf`
10. Add `ops/nginx/http-rate-limit.conf` directives to `/etc/nginx/nginx.conf` inside `http { ... }`
11. Run `sudo nginx -t` and reload Nginx
12. Enable and start Gunicorn

## Backups

Minimum recommended disaster recovery posture:

- off-droplet PostgreSQL backups
- droplet snapshot or backup enabled in DigitalOcean
- `.env` values stored somewhere recoverable outside the droplet

Because source datasets can be reloaded, the most critical state is the PostgreSQL database and server configuration.
