FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py index.html status.html deploy-log.json ./

ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

EXPOSE 8080
CMD ["python", "app.py"]
