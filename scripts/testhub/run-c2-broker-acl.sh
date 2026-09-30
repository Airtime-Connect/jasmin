#!/usr/bin/env bash
# AIR-1353: disposable RabbitMQ topic ACL proof; never configures a target broker.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="${ATC_C2_BROKER_PYTHON:-python3}"
IMAGE='rabbitmq:3.13-management-alpine@sha256:606d8c0d6b3c18d1da9afc53bc7cdb2a8d5486df91b5a9830e9e07626c9ae281'
"$PYTHON_BIN" -c 'import pika' >/dev/null
command -v docker >/dev/null
command -v openssl >/dev/null

cookie="$(openssl rand -hex 24)"
container_name="atc-testhub-c2-acl-$$"
docker run -d --name "$container_name" -p 127.0.0.1::5672 \
  -e RABBITMQ_ERLANG_COOKIE="$cookie" "$IMAGE"
unset cookie
cleanup() { docker rm -f "$container_name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

ready=0
for _ in {1..60}; do
  # Starting rabbitmq-diagnostics before entrypoint creates/chowns the cookie
  # can race with the server and leave a root-owned unreadable cookie.
  if docker exec -u rabbitmq "$container_name" \
      test -r /var/lib/rabbitmq/.erlang.cookie >/dev/null 2>&1 \
      && docker exec "$container_name" rabbitmq-diagnostics -q check_running >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo 'disposable RabbitMQ did not become ready' >&2
  docker logs "$container_name" --tail 25 >&2 || true
  exit 1
fi

docker exec "$container_name" rabbitmqctl add_vhost atc-c2-local >/dev/null
docker exec "$container_name" rabbitmqctl add_user c2_internal local-only-internal >/dev/null
docker exec "$container_name" rabbitmqctl add_user c2_unscoped local-only-unscoped >/dev/null
docker exec "$container_name" rabbitmqctl add_user c2_untrusted local-only-untrusted >/dev/null
docker exec "$container_name" rabbitmqctl set_permissions -p atc-c2-local \
  c2_internal '.*' '.*' '.*' >/dev/null
docker exec "$container_name" rabbitmqctl set_permissions -p atc-c2-local \
  c2_unscoped '^$' '^messaging$' '^$' >/dev/null
docker exec "$container_name" rabbitmqctl set_permissions -p atc-c2-local \
  c2_untrusted '^$' '^messaging$' '^$' >/dev/null
docker exec "$container_name" rabbitmqctl set_topic_permissions -p atc-c2-local \
  c2_untrusted messaging '^sandbox\..*$' '^$' >/dev/null

port_output="$(docker port "$container_name" 5672/tcp)"
[[ "$port_output" == 127.0.0.1:* ]] || {
  echo 'RabbitMQ fixture is not bound to loopback only' >&2
  exit 1
}
port="${port_output##*:}"
"$PYTHON_BIN" "$REPO/scripts/testhub/c2_broker_acl_probe.py" "$port"
