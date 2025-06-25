FROM python:3.10.0-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /usr/local/bin/
COPY setup_ssh_keys.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/setup_ssh_keys.sh

COPY . .

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "server.py"]
