FROM registry.red-soft.ru/ubi8/ubi-minimal:8.0.2-260324
ARG PYTHON_VERSION=3.14.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/python

RUN dnf update -y && dnf install -y curl ca-certificates tar gzip findutils && dnf clean all

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

RUN uv python install ${PYTHON_VERSION} && uv python pin ${PYTHON_VERSION}

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN uv pip install --system -r /app/backend/requirements.txt

COPY . /app

RUN chmod +x /app/docker/backend/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/docker/backend/entrypoint.sh"]
