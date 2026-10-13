#!/bin/bash
set -euo pipefail

mkdir -p /var/uploads /var/log/CTFd
chown -R 1001:1001 /var/uploads /var/log/CTFd
exec runuser -u ctfd -- /opt/CTFd/docker-entrypoint.sh
