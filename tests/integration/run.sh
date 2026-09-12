#!/usr/bin/env bash
# End-to-end integration test against a live app + client docker pair.
#
# Prerequisites:
#   - app container 'nas-app' is up (just up)
#   - a client container exists (just client-up pc1 && just client-setup pc1)
#
# Usage: tests/integration/run.sh [client-container]
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
CLIENT="${1:-ss-client-pc1}"
PASS="pw$(date +%s)"
SUFFIX="$(date +%s)"

jget() { python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

ADMIN_TOKEN="$(curl -s -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jget "['access_token']")"
[ -n "$ADMIN_TOKEN" ] || fail "admin login"
AUTH="Authorization: Bearer $ADMIN_TOKEN"
H='Content-Type: application/json'
POST() { curl -s -X POST -H "$AUTH" -H "$H" "$@"; }
GET() { curl -s -H "$AUTH" "$@"; }
DEL() { curl -s -X DELETE -H "$AUTH" "$@"; }

user_a="alice_$SUFFIX"
user_b="bob_$SUFFIX"
user_x="temp_$SUFFIX"
group="team_$SUFFIX"
share="share_$SUFFIX"

cleanup() {
  for obj in "$uid_a" "$uid_b" "$uid_x"; do
    [ -n "$obj" ] && DEL "$BASE/api/v1/users/$obj" >/dev/null || true
  done
  [ -n "$gid" ] && DEL "$BASE/api/v1/groups/$gid" >/dev/null || true
  [ -n "$sid" ] && DEL "$BASE/api/v1/shares/$sid" >/dev/null || true
}
trap cleanup EXIT

echo "== creating users '$user_a','$user_b','$user_x', group '$group', share '$share'"
uid_a="$(POST "$BASE/api/v1/users" -d "{\"username\":\"$user_a\",\"password\":\"$PASS\"}" | jget "['id']")"
uid_b="$(POST "$BASE/api/v1/users" -d "{\"username\":\"$user_b\",\"password\":\"$PASS\"}" | jget "['id']")"
uid_x="$(POST "$BASE/api/v1/users" -d "{\"username\":\"$user_x\",\"password\":\"$PASS\"}" | jget "['id']")"
gid="$(POST "$BASE/api/v1/groups" -d "{\"name\":\"$group\"}" | jget "['id']")"
sid="$(POST "$BASE/api/v1/shares" -d "{\"name\":\"$share\"}" | jget "['id']")"
[ -n "$uid_a" ] && [ -n "$gid" ] && [ -n "$sid" ] || fail "object creation"

POST "$BASE/api/v1/groups/$gid/shares" -d "{\"share_id\":\"$sid\"}" >/dev/null
POST "$BASE/api/v1/groups/$gid/members" -d "{\"user_id\":\"$uid_a\",\"access_level\":\"rw\"}" >/dev/null
POST "$BASE/api/v1/groups/$gid/members" -d "{\"user_id\":\"$uid_b\",\"access_level\":\"ro\"}" >/dev/null
POST "$BASE/api/v1/groups/$gid/members" \
  -d "{\"user_id\":\"$uid_x\",\"access_level\":\"ro\",\"expires_at\":\"2020-01-01T00:00:00Z\"}" >/dev/null

echo "== verifying registry"
docker exec nas-app net conf listshares | grep -qx "$share" || fail "share not in registry"
docker exec nas-app net conf showshare "$share" | grep -q "$user_x" || fail "temp user missing from valid users before sweep"

echo "== client write checks (rw=$user_a, ro=$user_b)"
docker exec "$CLIENT" bash -c "echo hello-integration > /tmp/integ.txt"
docker exec "$CLIENT" smbclient "//nas/$share" -U "$user_a%$PASS" -c "put /tmp/integ.txt wrote-by-a.txt" \
  >/dev/null || fail "rw user could not write"
if docker exec "$CLIENT" smbclient "//nas/$share" -U "$user_b%$PASS" -c "put /tmp/integ.txt denied-by-b.txt" >/dev/null 2>&1; then
  fail "ro user could write"
fi
echo "  rw write ok, ro write denied"

echo "== expiry sweep"
PROCESSED="$(POST "$BASE/api/v1/expirations/sweep" | jget "['processed']")"
[ "$PROCESSED" -ge 1 ] || fail "sweep processed 0 expirations"
docker exec nas-app net conf showshare "$share" | grep -q "$user_x" && fail "temp user still in valid users after sweep"
MEMBERS="$(GET "$BASE/api/v1/groups/$gid/members")"
echo "$MEMBERS" | grep -q "$user_x" && fail "temp user still a member after sweep"
echo "  temp access revoked"

echo "== mount-script generation"
MOUNT="$(POST "$BASE/api/v1/users/$user_a/mount-script" -d "{\"password\":\"$PASS\"}")"
SHARE_NAME="$share" python3 -c "
import json, os, sys
d = json.load(sys.stdin)
share = os.environ['SHARE_NAME']
assert d['shares'] and d['shares'][0]['access'] == 'RW', d
assert 'mount -t cifs //nas/' + share + ' /mnt/' + share in d['linux_script'], d
path = d['shares'][0]['path']
assert 'net use Z: ' + path + ' /user:' in d['windows_script'], d
" <<<"$MOUNT" || fail "mount-script content wrong"
ERR="$(POST "$BASE/api/v1/users/$user_a/mount-script" -d '{"password":"wrong-password"}' | jget "['error']")"
[ "$ERR" = "unauthorized" ] || fail "wrong password not rejected"
echo "  mount-script ok (rw user)"

echo "== cleanup"
DEL "$BASE/api/v1/users/$uid_a" >/dev/null
DEL "$BASE/api/v1/users/$uid_b" >/dev/null
DEL "$BASE/api/v1/users/$uid_x" >/dev/null
DEL "$BASE/api/v1/groups/$gid" >/dev/null
DEL "$BASE/api/v1/shares/$sid" >/dev/null

echo "== verifying cleanup"
GET "$BASE/api/v1/users" | grep -q "\"$user_a\"" && fail "user '$user_a' still exists"
GET "$BASE/api/v1/users" | grep -q "\"$user_b\"" && fail "user '$user_b' still exists"
GET "$BASE/api/v1/groups" | grep -q "\"$group\"" && fail "group '$group' still exists"
docker exec nas-app net conf listshares | grep -qx "$share" && fail "share still in registry"
echo "  cleanup verified"

echo "PASS: integration ok (share=$share)"