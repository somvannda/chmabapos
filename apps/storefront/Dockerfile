# Chmaba storefront: a server-rendered React Router v7 app.
#
# Unlike apps/web and apps/admin, which are static Vite bundles served by nginx,
# this app renders on the server and therefore needs a Node runtime. It ships as
# its own service (see deploy/docker-compose.prod.yml) instead of being a stage
# of Dockerfile.front.
#
# The whole checkout is copied because tailwind.config.js and app.css reach into
# packages/ui by relative path, exactly as they do in CI.

# ---------- Build ----------
FROM node:20-alpine AS build
WORKDIR /repo
COPY . .
RUN cd apps/storefront && npm ci
# The browser talks to the storefront host's own /api path, which the edge
# proxies to the API container; only the SSR process needs the internal URL, and
# that is supplied at runtime rather than baked in here.
#
# Vite inlines VITE_* at BUILD time, so the public provider values must be present
# here or the sign-in buttons stay hidden no matter what deploy/.env says. Same
# pattern as VITE_TURNSTILE_SITE_KEY on the web image.
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_TELEGRAM_BOT_USERNAME=
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_TELEGRAM_BOT_USERNAME=$VITE_TELEGRAM_BOT_USERNAME
RUN cd apps/storefront && npm run build

# ---------- Runtime ----------
FROM node:20-alpine AS runtime
WORKDIR /repo/apps/storefront

ENV NODE_ENV=production
ENV PORT=3000

# Production dependencies only. package-lock.json is copied with package.json so
# the install is pinned to the same tree CI verified.
COPY --from=build /repo/apps/storefront/package.json ./package.json
COPY --from=build /repo/apps/storefront/package-lock.json ./package-lock.json
RUN npm ci --omit=dev --no-audit --no-fund

COPY --from=build /repo/apps/storefront/build ./build

# Run unprivileged; the node image already provides this user.
USER node

EXPOSE 3000
CMD ["npx", "react-router-serve", "./build/server/index.js"]
