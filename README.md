# DIAL Adapter for DIAL

## Overview

The project implements application which adapts calls from one DIAL Core to calls to another DIAL Core.

Useful for local DIAL development against remote DIAL Core.
See the [example](./docker-compose/local/README.md) of such a setup.

## Development

### Development Environment

This project requires [Python ≥3.11](https://www.python.org/downloads/) and [Poetry ≥2.1.1](https://python-poetry.org/) for dependency management.

### Setup

1. Install Poetry. See the official [installation guide](https://python-poetry.org/docs/#installation).

2. *(Optional)* Specify custom Python or Poetry executables in `.env.dev`. This is useful if multiple versions are installed. By default, `python` and `poetry` are used.

   ```sh
   POETRY_PYTHON=path-to-python-exe
   POETRY=path-to-poetry-exe
   ```

3. Create and activate the virtual environment:

   ```sh
   make init_env
   source .venv/bin/activate
   ```

4. Install project dependencies (including linting, formatting, and test tools):

   ```sh
   make install
   ```

### IDE configuration

The recommended IDE is [VS Code](https://code.visualstudio.com/).
Open the project in VS Code and install the recommended extensions.
VS Code is configured to use the [Ruff formatter](https://docs.astral.sh/ruff/formatter/).

Alternatively you can use [PyCharm](https://www.jetbrains.com/pycharm/) that has built-in [Ruff support](https://www.jetbrains.com/help/pycharm/lsp-tools.html#ruff).

## Run

Run the development server:

```sh
make serve
```

### Make on Windows

As of now, Windows distributions do not include the make tool. To run make commands, the tool can be installed using
the following command (since [Windows 10](https://learn.microsoft.com/en-us/windows/package-manager/winget/)):

```sh
winget install GnuWin32.Make
```

For convenience, the tool folder can be added to the PATH environment variable as `C:\Program Files (x86)\GnuWin32\bin`.
The command definitions inside Makefile should be cross-platform to keep the development environment setup simple.

## Environment Variables

Copy `.env.example` to `.env` and customize it for your environment:

|Variable|Default|Description|
|---|---|---|
|LOG_LEVEL|INFO|Application log level. Use DEBUG for dev purposes and INFO in prod|
|WEB_CONCURRENCY|1|Number of workers for the server|
|DIAL_URL||URL of the **local** DIAL Core server used for development|
|HEADERS_TO_PROXY|`Accept`|Comma-separated list of headers to pass through to the upstream.|

### Logging

Logging is provided by the DIAL SDK. The `LOG_LEVEL` variable sets the severity threshold for the adapter's logs (`INFO` by default; use `DEBUG` for development).

By default logs are emitted as human-readable text.
Set `DIAL_SDK_LOG_FORMAT=json` for structured JSON logging.
The format is controlled by `DIAL_SDK_TEXT_LOG_FORMAT` / `DIAL_SDK_JSON_LOG_FORMAT` (both optional),
which use Python's `%`-style [logging attributes](https://docs.python.org/3/library/logging.html#logrecord-attributes)
and default to the values shown below.

Text logging (default):

```txt
DIAL_SDK_LOG_FORMAT=text
DIAL_SDK_TEXT_LOG_FORMAT='%(levelprefix)s | %(asctime)s | %(name)s | %(process)d | %(message)s'
```

Structured JSON logging:

```txt
DIAL_SDK_LOG_FORMAT=json
DIAL_SDK_JSON_LOG_FORMAT='{"level": "%(levelname)s", "time": "%(asctime)s", "logger": "%(name)s", "process": "%(process)d", "message": "%(message)s"}'
```

See the [full logging documentation](https://github.com/epam/ai-dial-sdk/blob/0.38.0/docs/logging.md) for details.

### Docker

Run the server in Docker:

```sh
make docker_serve
```

## Lint

Run the linting before committing:

```sh
make lint
```

To auto-fix formatting issues run:

```sh
make format
```

## Test

Run unit tests locally:

```sh
make test
```

## Clean

To remove the virtual environment and build artifacts:

```sh
make clean
```

### Git hooks

You may optionally install Git hooks that will automatically run the linting step on Git push. You only need to do it once for the given repository.

```sh
make install_git_hooks
```

> [!IMPORTANT]
> This command doesn't work if you have already installed Git hooks locally or globally.
