FROM python:3.12.6-alpine

WORKDIR /app

COPY ./src .
COPY requirements.txt ./

RUN apk add --no-cache gcc postgresql-dev musl-dev && \
  pip install --no-cache-dir -r requirements.txt

CMD ["python", "dmarc-exporter.py"]
