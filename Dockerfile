# Internal-only static hosting of the visualizer via Caddy.
# All libraries and preset packs are vendored in src/vendor/, so the
# image is fully self-contained — no network access needed at runtime.
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY src /srv

EXPOSE 80 443

RUN adduser -D -u 1000 appuser && chown -R 1000:1000 /srv
USER 1000
