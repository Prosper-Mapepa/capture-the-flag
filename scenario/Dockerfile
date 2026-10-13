FROM python:3.12-slim

WORKDIR /app
COPY server.py /app/server.py
COPY static /app/static

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8080
CMD ["python", "-u", "server.py"]
