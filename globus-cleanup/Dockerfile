FROM python:3.12-slim

RUN pip install --no-cache-dir "globus-cli>=3.44,<4" "requests>=2.31,<3"

# Non-root user. HOME must be writable: the Globus CLI caches tokens in ~/.globus/cli/
RUN useradd --uid 1000 --create-home --home-dir /home/app app
WORKDIR /app

COPY requirements.txt /app/
COPY scicat_globus_cleaner.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

RUN pip install --no-cache-dir -r requirements.txt

USER 1000
ENV HOME=/home/app PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]
