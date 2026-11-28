FROM python:3.15-slim@sha256:08a4c22c92b79ec821a7ad49768480039ee5b7accac3955228e75366e30abc8e
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/app
# copy and install dependencies
COPY requirements.txt copy_public_ds.py ./
RUN pip install -r requirements.txt

CMD ["python", "copy_public_ds.py"]
