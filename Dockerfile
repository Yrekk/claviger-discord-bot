FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 claviger \
    && useradd \
        --uid 10001 \
        --gid claviger \
        --create-home \
        --shell /usr/sbin/nologin \
        claviger

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

USER claviger

CMD ["claviger"]
