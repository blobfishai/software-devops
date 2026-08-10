FROM python:3.12-slim
WORKDIR /app
COPY world/ world/
COPY serve.py .
EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"
CMD ["python", "serve.py", "--world", "world", "--port", "8080"]
