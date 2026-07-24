# Next.js standalone production image for the web-next Railway service.
# NEXT_PUBLIC_API_BASE is inlined into the client bundle at BUILD time → pass it as a
# Railway build variable (point it at the public bff-api URL).
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
# Next.js standalone binds to $HOSTNAME; Docker/Railway set that to the container ID, so the
# server would listen only on the container's own address and fail the platform healthcheck.
# Force 0.0.0.0 at launch (a command-level assignment wins over the inherited HOSTNAME).
CMD ["sh", "-c", "HOSTNAME=0.0.0.0 node server.js"]
