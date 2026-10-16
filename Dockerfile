# Install only the dependencies needed to render Markdown and equations.
FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

# Use the same archive validation and build as GitHub Pages.
FROM python:3.12-alpine AS build
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY tools/ ./tools/
COPY tests/*.py ./tests/
COPY content/ ./content/
COPY incoming/ ./incoming/
COPY site/ ./site/
COPY audio/ ./audio/
COPY preferences.json ./preferences.json
RUN python -m unittest discover -s tests
RUN python tools/build.py

# The preview image contains the finished site and a static HTTP server.
FROM python:3.12-alpine AS preview
WORKDIR /site
COPY --from=build /app/dist/ ./
USER 65534:65534
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/data/archive.json', method='HEAD'), timeout=2).close()"
CMD ["python", "-m", "http.server", "8080", "--bind", "0.0.0.0", "--directory", "/site"]
