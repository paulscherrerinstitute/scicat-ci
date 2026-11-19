# dev image
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS dev
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/retention
# install python dependecies
RUN pip install poetry \
    && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi \
    && poetry export -f requirements.txt --output requirements.txt


# prod image
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS prod
WORKDIR /usr/src/retention
# copy and install dependencies
COPY --from=dev /usr/src/retention/requirements.txt ./
RUN pip install -r requirements.txt
# copy app sources
COPY ./src/*.py ./
