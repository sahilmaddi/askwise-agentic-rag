FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# nginx renders templates with environment variables at start-up, so the API address is set per platform:
# Docker Compose and Kubernetes use http://api:8000, Azure Container Apps the API app's internal URL.
ENV API_URL=http://api:8000
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
