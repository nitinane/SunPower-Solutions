FROM python:3.12.10-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
FROM base AS dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
FROM base AS runtime
RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p /app/storage && chown -R app:app /app
COPY --from=dependencies /usr/local /usr/local
COPY --chown=app:app . .
RUN chmod +x /app/entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
