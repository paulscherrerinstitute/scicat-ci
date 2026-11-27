# dev image
FROM python:3.13-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50 AS dev
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/retention
# install python dependecies
RUN pip install poetry \
    && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi \
    && poetry export -f requirements.txt --output requirements.txt


# prod image
FROM python:3.13-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50 AS prod
WORKDIR /usr/src/retention
# copy and install dependencies
COPY --from=dev /usr/src/retention/requirements.txt ./
RUN pip install -r requirements.txt
# copy app sources
COPY ./src/*.py ./
