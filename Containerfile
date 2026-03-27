FROM python:3.12-slim

WORKDIR /opt/operator

COPY pyproject.toml .
COPY orbit_operator/ orbit_operator/

RUN pip install --no-cache-dir .

USER 1001

ENTRYPOINT ["kopf", "run", "--standalone", "--all-namespaces", "--liveness=http://0.0.0.0:8080/healthz", "orbit_operator/main.py"]
