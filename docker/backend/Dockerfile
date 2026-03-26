FROM registry.red-soft.ru/ubi8/ubi-minimal:8.0.2-260324
ARG PYTHON_VERSION=3.14.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/python

RUN dnf update -y && dnf install -y curl ca-certificates tar gzip findutils && dnf clean all

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

RUN uv python install ${PYTHON_VERSION} && uv python pin ${PYTHON_VERSION}
ENV PYTHON_HOME=/opt/python/cpython-${PYTHON_VERSION}-linux-x86_64-gnu
RUN "${PYTHON_HOME}/bin/python" -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PYTHON_HOME}/bin:${PATH}"

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -U -r /app/backend/requirements.txt

COPY . /app

RUN chmod +x /app/docker/backend/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/docker/backend/entrypoint.sh"]
