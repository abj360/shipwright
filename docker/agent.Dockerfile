FROM python:3.12-slim

# docker CLI is required to launch sibling sandbox containers via the mounted socket
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY agent ./agent
COPY sandbox ./sandbox
COPY security ./security
COPY tui ./tui
RUN pip install --no-cache-dir .

# The interface is the default entrypoint; the CLI stays reachable as `shipwright`.
CMD ["ship", "--repo", "/workspace"]
