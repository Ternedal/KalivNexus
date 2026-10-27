FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY nexus ./nexus
RUN pip install --no-cache-dir .
RUN useradd -u 10001 -m nexus && mkdir /data && chown nexus:nexus /data
USER nexus
ENV NEXUS_DB=/data/nexus.db
EXPOSE 8088
CMD ["uvicorn", "nexus.main:app", "--host", "0.0.0.0", "--port", "8088"]
