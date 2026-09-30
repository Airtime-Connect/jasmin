#!/bin/bash
set -e

# Change binding host:port for redis, and amqp
sed -i "/\[redis-client\]/,/host=/  s/host=.*/host=$REDIS_CLIENT_HOST/" ${CONFIG_PATH}/jasmin.cfg
sed -i "/\[redis-client\]/,/port=/  s/port=.*/port=$REDIS_CLIENT_PORT/" ${CONFIG_PATH}/jasmin.cfg
sed -i "/\[amqp-broker\]/,/host=/  s/host=.*/host=$AMQP_BROKER_HOST/" ${CONFIG_PATH}/jasmin.cfg
sed -i "/\[amqp-broker\]/,/port=/  s/port=.*/port=$AMQP_BROKER_PORT/" ${CONFIG_PATH}/jasmin.cfg

echo 'Cleaning lock files'
rm -f /tmp/*.lock

if [ "${JASMIN_TESTHUB_C2_REQUIRED:-0}" != 0 ] || [ -n "${JASMIN_TESTHUB_C2_FACTORY:-}" ]; then
  case "$1" in
    jasmind.py|*/jasmind.py) ;;
    *) echo 'C2 startup requires jasmind.py' >&2; exit 1 ;;
  esac
  # The main daemon repeats this check with its own authority instance.
  python -m jasmin.managers.testhub_c2_entrypoint_preflight "${@:2}"
fi


if [ "$2" = "--enable-interceptor-client" ]; then
  echo 'Starting interceptord'
  interceptord.py &
fi

echo 'Starting jasmind'
exec "$@"
