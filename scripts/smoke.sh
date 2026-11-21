#!/usr/bin/env bash
set -euo pipefail

base_url="${DEVBOX_URL:-http://localhost:8100}"
run_id="${DEVBOX_SMOKE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"

wait_for() {
  local event_id="$1"
  local expected_status="$2"
  for _ in $(seq 1 45); do
    local status
    status="$(curl --fail --silent "$base_url/events/$event_id" | python -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
    if [[ "$status" == "$expected_status" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "Event $event_id did not reach $expected_status" >&2
  return 1
}

for _ in $(seq 1 45); do
  if curl --fail --silent "$base_url/health" >/dev/null; then break; fi
  sleep 2
done
curl --fail --silent "$base_url/health" >/dev/null

headers=(-H 'content-type: application/json' -H "Idempotency-Key: devbox-smoke-retry-$run_id")
body='{"kind":"ci.smoke","payload":{"run":"github-actions"}}'
first="$(curl --fail --silent -X POST "$base_url/events" "${headers[@]}" -d "$body")"
second="$(curl --fail --silent -X POST "$base_url/events" "${headers[@]}" -d "$body")"
event_id="$(python -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$first")"
retry_id="$(python -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$second")"
[[ "$event_id" == "$retry_id" ]]
if curl --silent -o /dev/null -w '%{http_code}' -X POST "$base_url/events" "${headers[@]}" -d '{"kind":"ci.smoke","payload":{"run":"different-request"}}' | grep -q '^409$'; then
  :
else
  echo "Reusing an idempotency key with a different payload should return HTTP 409" >&2
  exit 1
fi
wait_for "$event_id" processed

due_at="$(python -c 'from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat())')"
scheduled="$(curl --fail --silent -X POST "$base_url/events/scheduled" -H 'content-type: application/json' -H "Idempotency-Key: devbox-smoke-scheduled-$run_id" -d "{\"kind\":\"ci.reminder\",\"payload\":{\"case\":\"scheduler\"},\"scheduled_at\":\"$due_at\"}")"
scheduled_id="$(python -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$scheduled")"
wait_for "$scheduled_id" processed

for _ in $(seq 1 45); do
  if curl --fail --silent "$base_url/notifications" | grep -q "$scheduled_id"; then
    echo "Event processing, idempotent retry, scheduler, and notification flow passed."
    exit 0
  fi
  sleep 2
done
echo "Scheduled notification did not arrive" >&2
exit 1
