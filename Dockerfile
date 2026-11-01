# Channel Keeper in a container — for docker run on your own machine.
# On Railway railway.json pins Railway's own builder; if a service still builds from this file, it works too.
# Build: docker build -t channel-keeper .
# Run:   docker run -d --name channel-keeper --restart unless-stopped \
#          -e BOT_TOKEN=... -v channel-keeper-data:/data channel-keeper
# Runs as root inside the container on purpose: Railway mounts its volumes as root, and a non-root user
# could not write the bot's memory there (1.8.1 failed with «attempt to write a readonly database»).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "bot.main"]
