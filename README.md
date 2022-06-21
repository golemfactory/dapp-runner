# Golem dApp Runner

`dapp-runner` is a utility that allows you to run decentralized applications on Golem.
It uses simple application descriptors expressed in `yaml`, similar to those used by
tools like `docker-compose`.

`dapp-runner` runs alongside the [Golem daemon](https://github.com/golemfactory/yagna)
and uses [yapapi](https://github.com/golemfactory/yapapi), Golem's Python high-level API
to communicate with it. As opposed to using plain `yapapi` though, deployment of
applications on Golem using `dapp-runner` requires no code and no experience in Python.

## Quick start

### Yagna daemon

To run Golem apps, `dapp-runner` requires a properly configured yagna daemon.
In the future, you'll be able to provision apps using external supervisor machines
which will run a yagna daemon on your behalf.

For now, please follow the ["Requestor development: a quick primer"](https://handbook.golem.network/requestor-tutorials/flash-tutorial-of-requestor-development)
tutorial and ensure that your `yagna` is up and running. Only the first part of this
tutorial is required - you don't need to run the blender example.

Most importantly, make sure you have set the `YAGNA_APPKEY` in your evironment.

### Python environment

First, ensure you have Python 3.8 or later:

```bash
python3 --version
```

If you don't have `python3` or your Python is older than that, consider using [pyenv](https://github.com/pyenv/pyenv-installer).

Once your `python3` reports a version 3.8 or later, prepare your environment

```bash
python3 -m venv ~/.envs/dapp-runner
source ~/.envs/dapp-runner/bin/activate
```

or, if you're on Windows:

```shell
python -m venv --clear %HOMEDRIVE%%HOMEPATH%\.envs\dapp-runner
%HOMEDRIVE%%HOMEPATH%\.envs\dapp-runner\Scripts\activate.bat
```

### DApp runner

#### Clone the repository:

```bash
git clone --recurse-submodules https://github.com/golemfactory/dapp-runner.git
```

#### Install the dependencies

```
cd dapp-runner
pip install -U pip poetry
poetry install
```

#### Run an example application:

Make sure your `yagna` daemon is running,
you have initialized the payment driver with `yagna payment init --sender`,
and that you have set the `YAGNA_APPKEY` environment variable.

Then run:

```bash
dapp-runner start --config configs/default.yaml dapp-store/apps/webapp.yaml
```

You should see the application being deployed on the Golem Network and once it's up,
you'll be greeted with:

```
{"http": {"local_proxy_address": "http://localhost:8080"}}
```

You can connect to [this address](http://localhost:8080) using your local browser,
and you'll see our minimalistic web application example running.

Press Ctrl-C in the terminal where you ran `dapp-runner` to initiate its shutdown.

## Application descriptor

As mentioned above, the decentralized applications that are deployed on Golem by the
`dapp-runner` are described in `yaml` files, ultimately conforming to the schema
described in [GAP-16](https://github.com/golemfactory/golem-architecture/pull/39)
(currently with minor diversions).

### Example descriptor

Here's an example application descriptor (`http-proxy.yaml`), that provisions a single
instance of a simple, static website served with `nginx`:

```yaml
payloads:
  nginx:
    runtime: "vm"
    params:
      image_hash: "16ad039c00f60a48c76d0644c96ccba63b13296d140477c736512127"
nodes:
  http:
    payload: "nginx"
    entrypoint:
        - ["/docker-entrypoint.sh"]
        - ["/bin/chmod", "a+x", "/"]
        - ["/bin/sh", "-c", 'echo "Hello from inside Golem!" > /usr/share/nginx/html/index.html']
        - ["/bin/rm", "/var/log/nginx/access.log", "/var/log/nginx/error.log"]
        - ["/usr/sbin/nginx"]
    http_proxy:
      ports:
        - "80"  # specify just the remote port, allow the local port to be automatically chosen
```

Importantly, this example omits the definition of the `networks` object. As it specifies
the `http_proxy` element of a `nodes` entry, it causes the `dapp-runner` to implicitly
add the `networks` object with a default of a single IPv4 network. Additionally, it adds
the `vpn` capability to the requested parameters of the deployed `vm` runtime.

#### Web application

And here's an example of a slightly more complex application (`webapp.yaml`), that uses
two kinds of services and explicitly connects them within a specified network:

```yaml
payloads:
  db:
    runtime: "vm"
    params:
      image_hash: "85021afecf51687ecae8bdc21e10f3b11b82d2e3b169ba44e177340c"
  http:
    runtime: "vm"
    params:
      image_hash: "c37c1364f637c199fe710ca62241ff486db92c875b786814c6030aa1"
nodes:
  db:
    payload: "db"
    entrypoint:
      - ["/bin/run_rqlite.sh"]
    network: "default"
    ip:
      - "192.168.0.2"
  http:
    payload: "http"
    entrypoint:
      - ["/bin/bash", "-c", "cd /webapp && python app.py --db-address 192.168.0.2 --db-port 4001 initdb"]
      - ["/bin/bash", "-c", "cd /webapp && python app.py --db-address 192.168.0.2 --db-port 4001 run > /webapp/out 2> /webapp/err &"]
    http_proxy:
      ports:
        - "5000"  # specify just the remote port, allow the local port to be automatically chosen
    network: "default"
    ip:
      - "192.168.0.3"
    depends_on:
      - "db"
networks:
  default:
    ip: "192.168.0.0/24"
```

## Usage

Currently, the `dapp-runner` implements a single CLI command, `start`:

```
Usage: dapp-runner start [OPTIONS] DESCRIPTORS...
```

which allows the following options:

```
 -d, --data PATH    Path to the data file.
  -l, --log PATH     Path to the log file.
  -s, --state PATH   Path to the state file.
  --stdout PATH      Redirect stdout to the specified file.
  --stderr PATH      Redirect stderr to the specified file.
  -c, --config PATH  Path to the file containing yagna-specific config.
                     [required]
  --silent
  --help             Show this message and exit.
```

The `--data`, `--log`, `--state`, `--stdout`, and `--stderr` arguments specify the
locations of files to which the respective streams are written. If unspecified, all
streams are written to the console which the `dapp-runner` is invoked from.

### Streams

#### Data

The `data` stream consists of JSON-formatted output of specific components that are run
as part of the services. Currently it carries the command execution events from
exescript commands, e.g.:

```json
{"db": {"0": [{"command": {"run": {"entry_point": "/bin/run_rqlite.sh", "args": [], "capture": {"stdout": {"stream": {}}, "stderr": {"stream": {}}}}}, "success": true, "stdout": null, "stderr": null}]}}
```

and the parameters of any started instances of Local HTTP proxies:

```json
{"http": {"local_proxy_address": "http://localhost:8080"}}
```

The keys in the outermost dictionaries refer to names of service cluster as specified in
the `yaml` descriptor file. For exescript commands, the secondary layer's keys refer to
indices of instances within the specific cluster.

#### State

The `state` stream consists of JSON-formatted descriptions of the state of the dapp
after each state change, e.g.:

```json
{"db": {"0": "running"}, "http": {"0": "starting"}}
```

Here, again, the keys in the topmost dictionary refer to the names of service clusters
defined in the `yaml` descriptor file and the secondary layer's keys refer to indices
of specific instances.

#### Log

The `log` stream is a text stream of log messages emitted from `dapp-runner`.

#### Stdout / Stderr

Finally, `stdout` and `stderr` refer to the standard output streams of the `dapp-runner`
script.

### Config

This is a mandatory argument, specifying a path to a `yaml` file containing a
description of a configuration to connect to your `yagna` daemon, e.g.:

```yaml
yagna:
  app_key: "$YAGNA_APPKEY"
  subnet_tag: "devnet-beta"

payment:
  budget: 1.0  # GLM
  driver: "erc20"
  network: "rinkeby"
```

### Descriptors

One or more application descriptors, as specified in  the
["Application descriptor"](#application-descriptor) section above.

If more than one `yaml` descriptor file is given, all of the `yaml` files are merged
into one descriptor before being processed further by the `dapp-runner`. The files
are merged using a deep-merge strategy with contents of each subsequent `yaml` file
overriding the colliding keys of the former ones.
