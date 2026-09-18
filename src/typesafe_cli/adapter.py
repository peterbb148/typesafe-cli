"""The only provider boundary; SDK owns retries and client cleanup."""

import logging

import typesafe_sdk as sdk

from . import auth
from .errors import ConfigError
from .io import loads


def call(operation, *, timeout=30.0, retries=2, **kwargs):
    key, _ = auth.resolve()
    if key is None:
        raise ConfigError(
            "No API key configured. Run typesafe-cli auth login or set TYPESAFE_API_KEY."
        )
    # SDK debug logging includes request bodies. CLI never enables content logging.
    logging.getLogger("typesafe_sdk").disabled = True
    try:
        with sdk.TypeSafeClient(
            api_key=key,
            timeout=timeout,
            retry=sdk.RetryPolicy(max_retries=retries, timeout=60.0),
        ) as client:
            response = (
                client.models.list() if operation == "models" else client.system_one(**kwargs)
            )
            # Preserve future fields and metadata that typed SDK models otherwise ignore.
            return loads(response.raw_http_response.text)
    except sdk.TypeSafeAuthenticationError:
        message = (
            "Authentication failed; replace the API key with auth login or check TYPESAFE_API_KEY."
        )
    except sdk.TypeSafePermissionDeniedError:
        message = "Access denied; check the API key's account permissions."
    except sdk.TypeSafeRateLimitError:
        message = "Rate limit exhausted; wait before retrying or check your account limits."
    except sdk.TypeSafeAPITimeoutError:
        message = "Provider request timed out; retry later or adjust --timeout."
    except sdk.TypeSafeAPIConnectionError:
        message = "Cannot connect to TypeSafe; check your network and API endpoint."
    except sdk.TypeSafeAPIResponseValidationError:
        message = (
            "TypeSafe returned an invalid response; check service status and CLI compatibility."
        )
    except sdk.TypeSafeAPIError:
        message = (
            "TypeSafe rejected the request; check model access, questions, and service status."
        )
    except (sdk.TypeSafeError, ValueError, TypeError):
        message = (
            "Invalid SDK configuration or provider response; check endpoint and CLI compatibility."
        )
    raise ConfigError(message)
