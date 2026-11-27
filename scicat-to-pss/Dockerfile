FROM python:3.15-slim@sha256:63bb298d2b7b88f176f51b5189f54ce6535c997682ea70885d2132f5d473a8a5
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/app
# copy and install dependencies
COPY requirements.txt copy_public_ds.py ./
RUN pip install -r requirements.txt

CMD ["python", "copy_public_ds.py"]
