FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/app
# copy and install dependencies
COPY requirements.txt copy_public_ds.py ./
RUN pip install -r requirements.txt

CMD ["python", "copy_public_ds.py"]
