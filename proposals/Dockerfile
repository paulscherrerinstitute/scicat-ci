# build python swagger client sdk
FROM openjdk:slim as sdk
WORKDIR /root
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install curl \
    && curl https://repo1.maven.org/maven2/io/swagger/swagger-codegen-cli/2.2.3/swagger-codegen-cli-2.2.3.jar -o swagger-codegen-cli.jar
COPY swagger.json ./
RUN java -jar swagger-codegen-cli.jar generate -i swagger.json -l python -o swagger_client


# create wheel from python swagger client sdk
FROM python:3.8-alpine as wheel
WORKDIR /root
COPY --from=sdk /root/swagger_client ./
RUN python setup.py bdist_wheel -d /tmp


# dev image
FROM python:3.8-slim as dev
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/proposals
COPY --from=wheel /tmp/swagger_client-1.0.0-py3-none-any.whl ./
# install python dependecies
RUN pip install swagger_client-1.0.0-py3-none-any.whl \
    && pip install poetry \
    && poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi \
    && poetry export -f requirements.txt --output requirements.txt


# prod image
FROM python:3.8-slim AS prod
WORKDIR /usr/src/proposals
# copy and install dependencies
COPY --from=wheel /tmp/swagger_client-1.0.0-py3-none-any.whl ./
COPY --from=dev /usr/src/proposals/requirements.txt ./
RUN pip install -r requirements.txt \
    && pip install swagger_client-1.0.0-py3-none-any.whl
# copy app sources
COPY ./src/*.py ./
