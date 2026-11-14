#!/bin/sh
set -eu
case "${1:-server}" in
  migrate) exec python manage.py migrate --noinput ;;
  worker) exec taskiq worker core.taskiq:broker core.tasks ;;
  scheduler) exec taskiq scheduler core.taskiq:scheduler core.tasks ;;
  server) exec granian --interface asginl --host 0.0.0.0 --port "${PORT:-8000}" --loop uvloop --ws --static-path-route /static --static-path-mount ./staticfiles config.asgi:application ;;
  *) echo "Unknown mode: $1" >&2; exit 2 ;;
esac

