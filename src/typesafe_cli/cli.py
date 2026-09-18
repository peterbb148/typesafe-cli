"""Command definitions; keep data stdout separate from diagnostics."""

import functools
import math
import sys
from enum import StrEnum
from typing import Annotated

import typer

from . import __version__, adapter, auth
from .errors import ConfigError, InputError
from .io import emit, questions_input, state_input

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
auth_app = typer.Typer(no_args_is_help=True)
models_app = typer.Typer(no_args_is_help=True)
app.add_typer(auth_app, name="auth", help="Save, inspect, or remove authentication.")
app.add_typer(models_app, name="models", help="Discover provider models.")


def guarded(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (InputError, ConfigError) as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(2 if isinstance(error, InputError) else 1) from None

    return wrapped


def version(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version_flag: Annotated[
        bool, typer.Option("--version", callback=version, is_eager=True)
    ] = False,
):
    """Compose TypeSafe evaluations through JSON."""


@auth_app.command()
@guarded
def login(
    api_key_stdin: Annotated[bool, typer.Option(help="Read a key explicitly from stdin.")] = False,
):
    """Save an API key locally (no network validation)."""
    if api_key_stdin:
        key = sys.stdin.read()
    else:
        if not sys.stdin.isatty():
            raise InputError(
                "Interactive login requires a terminal; use --api-key-stdin explicitly."
            )
        key = typer.prompt("TypeSafe API key", hide_input=True, err=True)
    auth.save(key)
    emit(
        {
            "saved": True,
            "provider_validated": False,
            "environment_override_active": bool(auth.environment_key()),
        }
    )


@auth_app.command()
@guarded
def status():
    """Report local configuration without testing the key with the provider."""
    key, source = auth.resolve()
    emit({"configured": key is not None, "source": source, "provider_validated": False})


@auth_app.command()
@guarded
def logout():
    """Remove the saved key; environment overrides remain active."""
    emit(auth.logout())


Timeout = Annotated[
    float, typer.Option(min=0.001, max=300, help="HTTP operation timeout in seconds.")
]
Retries = Annotated[int, typer.Option(min=0, max=5, help="SDK retries after the initial attempt.")]


@models_app.command("list")
@guarded
def models_list(timeout: Timeout = 30.0, retries: Retries = 2):
    """Print the complete models response as JSON."""
    if not math.isfinite(timeout):
        raise InputError("Timeout must be finite.")
    emit(adapter.call("models", timeout=timeout, retries=retries))


class StateFormat(StrEnum):
    json = "json"
    text = "text"


@app.command()
@guarded
def evaluate(
    state: Annotated[str, typer.Option(help="State file, or - to read stdin.")],
    questions: Annotated[str, typer.Option(help="Named question map in a JSON file.")],
    state_format: StateFormat = StateFormat.json,
    model: Annotated[str, typer.Option(help="Model alias or explicit version.")] = "jev-latest",
    timeout: Timeout = 30.0,
    retries: Retries = 2,
):
    """Evaluate Choice, Score, and Noul questions together."""
    if not math.isfinite(timeout) or not model.strip():
        raise InputError("Use a finite timeout and a non-empty model.")
    parsed_state = state_input(state, state_format.value)
    parsed_questions = questions_input(questions)
    emit(
        adapter.call(
            "evaluate",
            state=parsed_state,
            questions=parsed_questions,
            model=model,
            timeout=timeout,
            retries=retries,
        )
    )
