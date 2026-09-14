# NAS Manager dev workflow (docker-only)
set shell := ["bash", "-c"]

COMPOSE := "docker compose -f compose.yml --project-directory .."
# Standalone test compose: isolated from the app service and the `nas` network
TEST_COMPOSE := "docker compose -f compose.tests.yml --project-directory .."
CLIENT_PREFIX := "ss-client"

default: help

## Show available recipes
help:
    @just --list

# ---------- Application ----------

## Build image and start app container
[working-directory: 'deploy']
up: build
    {{COMPOSE}} up -d


[working-directory: 'deploy']
ups: build
    {{COMPOSE}} up


## Stop and remove app container
[working-directory: 'deploy']
down:
    {{COMPOSE}} down

## Rebuild the app image
[working-directory: 'deploy']
build:
    {{COMPOSE}} build

## Restart app container (picks up code changes via bind-mount)
restart:
    docker restart nas-app

## Tail application logs
[working-directory: 'deploy']
logs:
    {{COMPOSE}} logs -f app

## Run unit tests in a one-off container (own compose, no shared network)
[working-directory: 'deploy']
test:
    {{TEST_COMPOSE}} run --rm test

## Run integration tests against the live app (needs a client up + setup first)
integration name:
    bash tests/integration/run.sh {{CLIENT_PREFIX}}-{{name}}

## Run an arbitrary command inside the app container (uv-aware)
app-exec +cmd:
    docker exec nas-app bash -lc "{{cmd}}"

# ---------- UI (web-ui) ----------

## Start the Quasar dev server (proxies /api to localhost:8000)
[working-directory: 'web-ui']
ui-dev:
    yarn dev

## Type-check the frontend
[working-directory: 'web-ui']
ui-typecheck:
    yarn typecheck

## Build the frontend production bundle
[working-directory: 'web-ui']
ui-build:
    yarn build

## Generate app icons (favicon) from a source PNG (path relative to web-ui/)
[working-directory: 'web-ui']
seticon source='../nas-manager.png':
    npx --yes @quasar/icongenie generate -m spa -i {{source}} --quality 8

# ---------- Clients ----------

## Start a test client container (e.g. just client-up pc1)
client-up name:
    docker network inspect nas >/dev/null 2>&1 || docker network create nas
    docker run -d --name {{CLIENT_PREFIX}}-{{name}} --hostname {{name}} \
      --privileged --network nas ubuntu:24.04 sleep infinity

## Stop and remove a client container
client-down name:
    docker rm -f {{CLIENT_PREFIX}}-{{name}}

## List running clients
clients:
    @docker ps --filter "name={{CLIENT_PREFIX}}-" --format {{ '{{.Names}} {{.Status}}' }}

## Install cifs/smb tooling inside a client (run once per client)
client-setup name:
    docker exec {{CLIENT_PREFIX}}-{{name}} bash -c \
      "apt-get update && apt-get install -y --no-install-recommends cifs-utils smbclient ca-certificates curl"

## Run an arbitrary command in a client container
client-exec name +cmd:
    docker exec {{CLIENT_PREFIX}}-{{name}} bash -lc "{{cmd}}"

# ---------- Share testing helpers (run inside a client) ----------

## List shares visible to USER from client: just smb-list pc1 alice secret
smb-list name user password:
    docker exec {{CLIENT_PREFIX}}-{{name}} \
      smbclient -L //nas -U "{{user}}%{{password}}"

## Mount a share inside client: just mount-share pc1 photos alice secret /mnt/photos
mount-share name share user password dest:
    docker exec {{CLIENT_PREFIX}}-{{name}} bash -c \
      "mkdir -p {{dest}} && mount -t cifs //nas/{{share}} {{dest}} -o username={{user}},password={{password}}"

## Unmount a share inside client: just umount-share pc1 /mnt/photos
umount-share name dest:
    docker exec {{CLIENT_PREFIX}}-{{name}} umount {{dest}}

# ---------- Registry smoke (prototype) ----------

## Show current shares in the Samba registry
smoke-registry:
    docker exec nas-app net conf listshares

# ---------- CLI ----------

## Build CLI for Linux (requires uv + nuitka)
cli-build-linux:
	bash cli/build_linux.sh

## Run CLI tests
cli-test:
	cd cli && uv run pytest -v

## Build CLI for Windows (run on Windows machine)
## cli-build-windows: run cli/build_windows.ps1 on Windows
