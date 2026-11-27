FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE 1
WORKDIR /usr/src/app
# copy and install dependencies
COPY requirements.txt copy_public_ds.py ./
RUN pip install -r requirements.txt

CMD ["python", "copy_public_ds.py"]
