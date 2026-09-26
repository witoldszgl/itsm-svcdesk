# svcdesk image: everything is installed at build time, nothing is fetched at run time.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SVCDESK_DB=/data/svcdesk.db

WORKDIR /app
COPY src/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/svcdesk ./svcdesk

RUN useradd --system --uid 10001 svcdesk && mkdir -p /data && chown svcdesk /data
USER svcdesk
VOLUME ["/data"]

EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=20 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "svcdesk.app:app", "--host", "0.0.0.0", "--port", "8080"]
