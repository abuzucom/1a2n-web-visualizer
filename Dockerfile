# Internal-only static hosting of the visualizer via Caddy.
# All libraries and preset packs are vendored in src/vendor/, so the
# image is fully self-contained — no network access needed at runtime.
# The digest pins the multi-arch caddy:2-alpine index. Dependabot does not
# watch Docker images here, so bump it by hand: read "digest" from
# https://hub.docker.com/v2/repositories/library/caddy/tags/2-alpine and
# replace the value below.
FROM caddy:2-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0

COPY Caddyfile /etc/caddy/Caddyfile
COPY src /srv

EXPOSE 80 443

RUN adduser -D -u 1000 appuser && chown -R 1000:1000 /srv
USER 1000
