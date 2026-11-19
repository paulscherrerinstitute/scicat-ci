# dev image
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS dev
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/proposals
# install python dependecies
RUN pip install poetry \
    && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi \
    && poetry export -f requirements.txt --output requirements.txt


# prod image
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS prod
WORKDIR /usr/src/proposals
# copy and install dependencies
COPY --from=dev /usr/src/proposals/requirements.txt ./
RUN pip install -r requirements.txt 
# copy app sources
COPY ./src/*.py ./
