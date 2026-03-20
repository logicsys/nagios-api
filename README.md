# Nagios API
nagios-api - presents a REST-like JSON interface to Nagios.

## Description
This program provides a simple REST-like interface to Nagios. Run this
on your Nagios host and then sit back and enjoy a much easier, more
straightforward way to accomplish things with Nagios. You can use the
bundled nagios-cli, but you may find it easier to write your own system
for interfacing with the API.

## Synopsis
`nagios-api [OPTIONS]`

## Dependencies
Dependencies include:

- flask
- requests
- waitress

Install via pip:

```
pip install -r requirements.txt
```

Or install the package directly:

```
pip install .
```

## Usage
Usage is pretty easy:

```
nagios-api -p 8080 -c /var/lib/nagios3/rw/nagios.cmd \
  -s /var/cache/nagios3/status.dat -l /var/log/nagios3/nagios.log
```

You must at least provide the status file options. If you don't provide
the other options, then we will disable that functionality and error to
clients who request it.

## Build, Lint & Test

All run in temporary containers (podman or docker) to avoid polluting the host.
A Makefile is provided for convenience:

```
make build              # Build dev image, verify package imports
make lint               # Run flake8 (auto-builds image if needed)
make test               # Run unit tests via pytest (auto-builds image if needed)
make integration-test   # Run integration tests (see below)
make audit              # Audit dependencies for vulnerabilities
make clean              # Remove the dev container image
```

Or call the scripts directly:

```
scripts/build.sh
scripts/lint.sh
scripts/test.sh
scripts/integration-test.sh
```

### Integration Tests

The integration test suite (`make integration-test`) builds a container that
compiles Nagios Core 4.5.11 and plugins from source, starts the Nagios daemon,
Apache (for CGI-based availability reports), and nagios-api, then runs 76
pytest tests against the live API. Tests cover:

- **Read endpoints** — `/state`, `/objects`, `/host`, `/service`, `/status`,
  `/problems`, `/log`
- **Write endpoints** — `submit_result`, `schedule_downtime`, `cancel_downtime`,
  `schedule_hostgroup_downtime`, `disable_notifications`, `enable_notifications`,
  `disable_checks`, `enable_checks`, `schedule_check`, `acknowledge_problem`,
  `remove_acknowledgement`, `add_comment`, `delete_comment`, `raw_command`,
  `restart_nagios`
- **State change verification** — passive check results, downtime lifecycle,
  acknowledgement lifecycle, comment lifecycle, notification toggling
- **Availability reports** — host and service availability via Nagios `avail.cgi`,
  period shorthands, custom timestamps, error handling
- **Security** — method enforcement (POST-only endpoints reject GET), unknown
  endpoint handling, information disclosure prevention

The first run takes a few minutes to compile Nagios; subsequent runs use the
cached image layer.

## Using the API
The server speaks [JSON](http://www.json.org/). You can either GET data from it or POST data to
it and take an action. It's pretty straightforward, here's an idea of
what you can do from the command line:

```
curl http://localhost:8080/state
```

That calls the `state` method and returns the JSON result.

```
curl -d '{"host": "web01", "duration": 600}' -H 'Content-Type: application/json' http://localhost:8080/schedule_downtime
```

This POSTs the given JSON object to the `schedule_downtime` method. You
will note that all objects returned follow a predictable format:

```
{"content": <object>, "success": <bool>}
```

The `success` field is always `true` or `false`, allowing you to
determine at a glance if the command succeeded. The `content` field may
be any valid JSON value: an int, string, null, bool, object, array,
etc. What is returned depends on the method being called.

## Using `nagios-cli`
Once your API server is up and running you can access it through the
included nagios-cli script. The script now has some decent built-in help
so you should be able to get all you need:

```
nagios-cli -h
```

The original raw JSON mode is still supported by passing the --raw
option.

## Options
Below are the options taken on the CLI.

```
-p, --port=PORT
```

Listen on port 'PORT' for HTTP requests (default: 6315).

```
-b, --bind=ADDR
```

Bind to ADDR for HTTP requests (defaults to `127.0.0.1`, localhost only).
Use `-b 0.0.0.0` to listen on all interfaces.

```
-c, --command-file=FILE
```

Use 'FILE' to write commands to Nagios. This is where external
commands are sent. If your Nagios installation does not allow
external commands, do not set this option.

```
-d, --config-directory=PATH
```

The directory in which Nagios will look for object files and import
hosts into its internal database for monitoring.

```
-s, --status-file=FILE
```

Set 'FILE' to the status file where Nagios stores its status
information. This is where we learn about the state of the world and
is the only required parameter.

```
-l, --log-file=FILE
```

Point 'FILE' to the location of Nagios's log file if you want to
allow people to subscribe to it.

```
-o, --allow-origin=ORIGIN
```

Sets the `Access-Control-Allow-Origin` header for CORS. Must be an
explicit origin URL (e.g., `https://monitoring.example.com`). Wildcard
`*` is rejected by default for security reasons. Use
`--allow-origin-unsafe-wildcard` to explicitly opt-in to wildcard mode.

```
--allow-origin-unsafe-wildcard
```

Allow `--allow-origin` to be set to `*`. This is insecure and should
only be used in development or isolated environments.

```
-q, --quiet
```

If present, we will only print warning/critical messages. Useful if
you are running this in the background.

```
-f, --pid-file=PID_FILE
```

File to write the process ID to (default: `/var/run/nagios-api.pid`).

```
-k, --api-key-file=FILE
```

File containing API keys (one per line, `#` comments and blank lines
ignored). When provided, all requests must include a valid key via the
`X-API-Key` header or `api_key` query parameter. Without this option,
no authentication is enforced.

```
--tls-cert=FILE
```

Path to TLS certificate file (PEM). Enables HTTPS. Must be used
together with `--tls-key`.

```
--tls-key=FILE
```

Path to TLS private key file (PEM). Required when using `--tls-cert`.

```
--rate-limit=RPS
```

Maximum requests per second per client IP (default: 0, unlimited).
When set, requests exceeding the limit receive a 429 response.

```
--rate-limit-burst=N
```

Burst size for the rate limiter (default: 20). Allows short bursts of
requests up to this count before rate limiting kicks in.

```
--dev
```

Use Flask's built-in development server instead of waitress. Not
recommended for production use.

## API
This program currently supports only a subset of the Nagios API. More
is being added as it is needed. If you need something that isn't here,
please consider submitting a patch!

This section is organized into methods and sorted alphabetically. Each
method is specified as a URL and may include an integer component on the
path. Most data is passed as JSON objects in the body of a POST.

### `acknowledge_problem`
This method allows you to acknowledge a given problem on a host or service.

```
{
  "host": "string",
  "service": "string",
  "comment": "string",
  "sticky": true,
  "notify": true,
  "persistent": true,
  "expire": 0,
  "author": "string"
}
```

#### Fields
`host` = `STRING [required]`

Which host to act on.

`service` = `STRING [optional]`

If specified, act on this service.

`comment` = `STRING [required]`

This is required and should contain some sort of message that explains why
this alert is being acknowledged.

`sticky` = `BOOL [optional]`

default TRUE. When true, this acknowledgement stays until the
host enters an OK state. If false, the acknowledgement clears on ANY state
change.

`notify` = `BOOL [optional]`

default TRUE. Whether or not to send a notification that this
problem has been acknowledged.

`persistent` = `BOOL [optional]`

default FALSE. If this is enabled, the comment given will stay
on the host or service. By default, when an acknowledgement expires, the
comment associated with it is deleted.

`expire` = `INTEGER [optional]`

default 0.  If set, it will (given icinga >= 1.6) expire the
acknowledgement at the given timestamp. Seconds since the UNIX epoch. Defaults
to 0 (off).

`author` = `STRING [optional]`

The name of the author. This is useful in UIs if you want
to disambiguate who is doing what.

### `add_comment`
For a given host and/or service, add a comment. This is free-form text that can
include whatever you want and is visible in the Nagios UI and API output.

```
{
  "host": "string",
  "service": "string",
  "comment": "string",
  "persistent": true,
  "author": "string"
}
```

#### Fields
`host` = `STRING [required]`

Which host to act on.

`service` = `STRING [optional]`

If specified, act on this service.

`comment` = `STRING [required]`

This is required and should contain the text of the comment you want to
add to this host or service.

`persistent` = `BOOL [optional]`

Optional, default FALSE. If this is enabled, the comment given will stay
on the host or service until deleted manually. By default, they only stay
until Nagios is restarted.

`author` = `STRING [optional]`

The name of the author. This is useful in UIs if you want
to disambiguate who is doing what.

### `cancel_downtime`
Very simply, this immediately lifts a downtime that is currently in
effect on a host or service. If you know the `downtime_id`, you can
specify that as a URL argument like this:

```
curl -d "{}" http://localhost:8080/cancel_downtime/15
```

That would cancel the downtime with `downtime_id` of 15. Most of the
time you will probably not have this information and so we allow you to
cancel by host/service as well.

```
{
  "host": "string",
  "service": "string",
  "services_too": true
}
```

#### Fields
`host` = `STRING [required]`

Which host to cancel downtime from.  This must be specified if you
are not using the `downtime_id` directly.

`service` = `STRING [optional]`

If specified, cancel any downtimes on this service.

`services_too` = `BOOL [optional]`

If true and you have not specified a `service` in
specific, then we will cancel all downtimes on this host and all of
the services it has.

### `disable_notifications`
This disables alert notifications on a host or service. (As an operational
note, you might want to schedule downtime instead. Disabling notifications
has a habit of leaving things off and people forgetting about it.)

```
{
  "host": "string",
  "service": "string"
}
```

#### Fields
`host` = `STRING [required]`

Which host to act on.

`service` = `STRING [optional]`

If specified, act on this service.

### `delete_comment`
Deletes comments from a host or service. Can be used to delete all comments or
just a particular comment.

```
{
  "host": "string",
  "service": "string",
  "comment_id": 1234
}
```

#### Fields
`host` = `STRING [required]`

Which host to act on.

`service` = `STRING [optional]`

If specified, act on this service.

`comment_id` = `INTEGER [required]`

The ID of the comment you wish to delete. You may set this to `-1` to delete
all comments on the given host or service.

### `enable_notifications`
This enables alert notifications on a host or service.

```
{
  "host": "string",
  "service": "string"
}
```

#### Fields
`host` = `STRING [required]`

Which host to act on.

`service` = `STRING [optional]`

If specified, act on this service.

### `log`
Simply returns the most recent 1000 items in the Nagios event log. These
are currently unparsed. There is a plan to parse this in the future and
return event objects.

### `status`
Simply returns a JSON that contains nagios status objects.

### `restart_nagios`
Restarts the nagios service. Requires a POST request (GET is rejected
for CSRF protection).

```
curl -d '{}' -H 'Content-Type: application/json' http://localhost:8080/restart_nagios
```

### `update_host`
This method will create/update a nagios configuration file that contains devices.

```
{
  "file_name": "string",
  "text": "string"
}
```

#### Fields
`file_name` = `STRING [required]`

File name for the configuration. Must end in `.cfg` and contain only
alphanumeric characters, hyphens, underscores, and dots. Path
separators are stripped for security.

`text` = `STRING [required]`

Content of the configuration file.

### `objects`
Returns a dict with the key being hostnames and the values being a list
of services defined for that host. Use this method to get the contents
of the world -- i.e., all hosts and services.

### `remove_acknowledgement`
This method cancels an acknowledgement on a host or service.

```
{
  "host": "string",
  "service": "string"
}
```

#### Fields
`host` = `STRING [required]`

Which host to act on.

`service` = `STRING [optional]`

If specified, act on this service.

### `schedule_check`
This API lets you schedule a check for a host or service. This also allows
you to force a check.

```
{
  "host": "string",
  "service": "string",
  "check_time": 1234,
  "forced": true,
  "output": "string"
}
```

#### Fields
`host` = `STRING [required]`

The host to schedule a check for. Required.

`service` = `STRING [optional]`

If present, we'll schedule a check on this service at the given
time.

`all_services` = `BOOL [optional]`

If present, we'll schedule a check on again all services at the given
time.

`check_time` = `INTEGER [optional]`

Optional, defaults to now. You can specify what time you want the check
to be run at.

`forced` = `BOOL [optional]`

Optional, defaults to FALSE. When true, then you force Nagios to run the
check at the given time. By default, Nagios will only run the check if it
meets the standard eligibility criteria.

`output` = `STRING [required]`

The plugin output to be displayed in the UI and stored.  This is a
single line of text, normally returned by checkers.

### `schedule_downtime`
This general purpose method is used for creating fixed length downtimes.
This method can be used on hosts and services. You are allowed to
specify the author and comment to go with the downtime, too. The JSON
parameters are:

```
{
  "host": "string",
  "duration": 1234,
  "service": "string",
  "services_too": true,
  "author": "string",
  "comment": "string"
}
```

#### Fields
`host` = `STRING [required]`

Which host to schedule a downtime for.  This must be specified.

`duration` = `INTEGER [required]`

How many seconds this downtime will last for. They begin immediately
and continue for `duration` seconds before ending.

`service` = `STRING [optional]`

If specified, we will schedule a downtime for this service
on the above host. If not specified, then the downtime will be
scheduled for the host itself.

`services_too` = `BOOL [optional]`

If true and you have not specified a `service` in
specific, then we will schedule a downtime for the host and all of
the services on that host. Potentially many downtimes are scheduled.

`author` = `STRING [optional]`

The name of the author. This is useful in UIs if you want
to disambiguate who is doing what.

`comment` = `STRING [optional]`

As above, useful in the UI.

The result of this method is a text string that indicates whether or
not the downtimes have been scheduled or if a different error occurred.
We do not have the ability to get the `downtime_id` that is generated,
unfortunately, as that would require waiting for Nagios to regenerate
the status file.

### `schedule_hostgroup_downtime`
This method is used for creating fixed length downtimes on all the hosts
belonging to a hostgroup. You are allowed to specify the author and comment
to go with the downtime, too. The JSON parameters are:

```
{
  "hostgroup": "string",
  "duration": 1234,
  "services_too": true,
  "author": "string",
  "comment": "string"
}
```

#### Fields
`hostgroup` = `STRING [required]`

Which hostgroup to schedule a downtime for. This must be specified.

`duration` = `INTEGER [required]`

How many seconds this downtime will last for. They begin immediately
and continue for `duration` seconds before ending.

`services_too` = `BOOL [optional]`

If true, then we will schedule a downtime for all the hosts in
the hostgroup and all of the services on those hosts.
Potentially many downtimes are scheduled.

`author` = `STRING [optional]`

The name of the author. This is useful in UIs if you want
to disambiguate who is doing what.

`comment` = `STRING [optional]`

As above, useful in the UI.

The result of this method is a text string that indicates whether or
not the downtimes have been scheduled or if a different error occurred.
We do not have the ability to get the `downtime_id` that is generated,
unfortunately, as that would require waiting for Nagios to regenerate
the status file.

### `state`
This method takes no parameters. It returns a large JSON object
containing all of the active state from Nagios. Included are all hosts,
services, downtimes, comments, and other things that may be in the
global state object.

### `submit_result`
If you are using passive service checks or you just want to submit a
result for a check, you can use this method to submit your result to
Nagios.

```
{
  "host": "string",
  "service": "string",
  "status": 1234,
  "output": "string"
}
```

#### Fields
`host` = `STRING [required]`

The host to submit a result for.  This is required.

`service` = `STRING [optional]`

If specified, we will submit a result for this service on
the above host. If not specified, then the result will be submitted
for the host itself.

`status` = `INTEGER [required]`

The status code to set this host/service check to. If you are
updating a host's status: 0 = OK, 1 = DOWN, 2 = UNREACHABLE. For
service checks, 0 = OK, 1 = WARNING, 2 = CRITICAL, 3 = UNKNOWN.

`output` = `STRING [required]`

The plugin output to be displayed in the UI and stored.  This is a
single line of text, normally returned by checkers.

The response indicates if we successfully wrote the command to the log.

## Docker
A Docker container is available for convenience. It needs to be run on
the same server as the nagios installation.

First determine the location of the `status.dat`, `nagios.log`, and
`nagios.cmd` files. Map these files into the Docker container. The
container can be started using the following command:

```
docker build -t nagios-api .
docker run -v /var/lib/nagios3/rw/nagios.cmd:/opt/nagios.cmd \
  -v /var/cache/nagios3/status.dat:/opt/status.dat \
  -v /var/log/nagios3/nagios.log:/opt/nagios.log \
  -p 8080:8080 nagios-api
```

Note: The container's default CMD passes `-b 0.0.0.0` to bind on all
interfaces (required for Docker networking). The default bind address
outside of Docker is `127.0.0.1` (localhost only).

## Author
Written by Mark Smith <mark@qq.is> while under the employ of Bump
Technologies, Inc.

## Copying
See the `LICENSE` file for licensing information.
