FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
# Use npm install instead of npm ci to handle missing lockfile gracefully
RUN npm install

COPY . .
RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY package*.json ./

# node:20-alpine already ships with user/group "node" (uid/gid 1000)
RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["npm", "start"]
