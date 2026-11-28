# dev image
FROM python:3.15-slim@sha256:08a4c22c92b79ec821a7ad49768480039ee5b7accac3955228e75366e30abc8e AS dev
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/proposals
# install python dependecies
RUN pip install poetry \
    && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi \
    && poetry export -f requirements.txt --output requirements.txt


# prod image
FROM python:3.15-slim@sha256:08a4c22c92b79ec821a7ad49768480039ee5b7accac3955228e75366e30abc8e AS prod
WORKDIR /usr/src/proposals
# copy and install dependencies
COPY --from=dev /usr/src/proposals/requirements.txt ./
RUN pip install -r requirements.txt 
# copy app sources
COPY ./src/*.py ./
