# Golem dApp Runner

`dapp-runner` is a utility that allows you to run decentralized applications on Golem.
It uses simple application descriptors expressed in `yaml` and similar to those used by
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
