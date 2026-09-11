FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        samba smbclient python3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --all-extras

ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1

COPY app ./app
COPY deploy/smb.conf.template ./deploy/smb.conf.template
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /mnt/share /data /var/lib/samba/private /var/log/samba

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
