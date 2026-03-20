#!/bin/bash
set -e

NAGIOS_HOME=/usr/local/nagios
STATUS_FILE=$NAGIOS_HOME/var/status.dat
CMD_FILE=$NAGIOS_HOME/var/rw/nagios.cmd
LOG_FILE=$NAGIOS_HOME/var/nagios.log
API_PORT=8080
API_PID_FILE=/tmp/nagios-api.pid

echo "==> Setting up Nagios directories..."
mkdir -p $NAGIOS_HOME/var/rw
mkdir -p $NAGIOS_HOME/var/archives
mkdir -p $NAGIOS_HOME/var/spool/checkresults
chown -R nagios:nagcmd $NAGIOS_HOME/var
chmod -R 775 $NAGIOS_HOME/var/rw

echo "==> Verifying Nagios configuration..."
$NAGIOS_HOME/bin/nagios -v $NAGIOS_HOME/etc/nagios.cfg
if [ $? -ne 0 ]; then
    echo "ERROR: Nagios config verification failed!"
    exit 1
fi

echo "==> Starting Nagios daemon..."
$NAGIOS_HOME/bin/nagios -d $NAGIOS_HOME/etc/nagios.cfg

# Wait for Nagios to create the status file and command pipe
echo "==> Waiting for Nagios to initialize..."
TIMEOUT=60
ELAPSED=0
while [ ! -f "$STATUS_FILE" ] || [ ! -p "$CMD_FILE" ]; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "ERROR: Nagios did not initialize within ${TIMEOUT}s"
        echo "  status.dat exists: $([ -f "$STATUS_FILE" ] && echo yes || echo no)"
        echo "  nagios.cmd exists: $([ -p "$CMD_FILE" ] && echo yes || echo no)"
        cat $LOG_FILE 2>/dev/null || true
        exit 1
    fi
done
echo "  Nagios ready after ${ELAPSED}s"

# Wait for status.dat to have host data (Nagios needs to run at least one check cycle)
echo "==> Waiting for Nagios to populate status data..."
ELAPSED=0
while ! grep -q "hoststatus" "$STATUS_FILE" 2>/dev/null; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "ERROR: Nagios did not populate status data within ${TIMEOUT}s"
        cat $STATUS_FILE 2>/dev/null | head -20
        exit 1
    fi
done
echo "  Status data populated after ${ELAPSED}s"

echo "==> Starting Apache for Nagios CGI..."
. /etc/apache2/envvars
apache2 -k start
echo "  Apache started"

echo "==> Starting nagios-api on port ${API_PORT}..."
python /opt/nagios-api/nagios-api \
    -p $API_PORT \
    -b 0.0.0.0 \
    -s "$STATUS_FILE" \
    -c "$CMD_FILE" \
    -l "$LOG_FILE" \
    -f "$API_PID_FILE" \
    -q \
    --nagios-cgi-url http://127.0.0.1/nagios/cgi-bin \
    --nagios-cgi-user nagiosadmin \
    --nagios-cgi-pass nagiosadmin &

API_PID=$!

# Wait for nagios-api to be ready
echo "==> Waiting for nagios-api to respond..."
ELAPSED=0
while ! python -c "import requests; requests.get('http://127.0.0.1:${API_PORT}/state')" 2>/dev/null; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ $ELAPSED -ge 30 ]; then
        echo "ERROR: nagios-api did not start within 30s"
        exit 1
    fi
done
echo "  nagios-api ready after ${ELAPSED}s"

echo "==> Running integration tests..."
cd /opt/nagios-api
python -m pytest tests/integration/ -v --tb=short "$@"
TEST_EXIT=$?

echo "==> Cleaning up..."
kill $API_PID 2>/dev/null || true
kill $(cat $NAGIOS_HOME/var/nagios.lock 2>/dev/null) 2>/dev/null || true

exit $TEST_EXIT
