FROM python:3.12-slim

WORKDIR /app

COPY requirements_api.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements_api.txt

COPY apisrc /app/src

# Run as an unprivileged user; the API only needs read access to its code.
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER 10001

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "src.service:app", "--host=0.0.0.0", "--port=8000"]
