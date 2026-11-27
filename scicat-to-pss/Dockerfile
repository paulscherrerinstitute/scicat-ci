FROM python:3.10-slim@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/app
# copy and install dependencies
COPY requirements.txt copy_public_ds.py ./
RUN pip install -r requirements.txt

CMD ["python", "copy_public_ds.py"]
