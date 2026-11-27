# dev image
FROM python:3.15-slim@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5 AS dev
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/retention
# install python dependecies
RUN pip install poetry \
    && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi \
    && poetry export -f requirements.txt --output requirements.txt


# prod image
FROM python:3.15-slim@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5 AS prod
WORKDIR /usr/src/retention
# copy and install dependencies
COPY --from=dev /usr/src/retention/requirements.txt ./
RUN pip install -r requirements.txt
# copy app sources
COPY ./src/*.py ./
