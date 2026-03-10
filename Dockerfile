ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

EXPOSE 8080

RUN apt-get update && \
    apt-get install -y --no-install-recommends libffi-dev libssl-dev gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /opt/nagios-api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps .

CMD ["python", "/opt/nagios-api/nagios-api", "-p", "8080", "-b", "0.0.0.0", "-s", "/opt/status.dat", "-c", "/opt/nagios.cmd", "-l", "/opt/nagios.log", "-q"]
