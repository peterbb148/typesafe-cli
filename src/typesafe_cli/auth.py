"""Explicit, private credential persistence; never log credential values."""

import json
import os
import stat
import tempfile
from pathlib import Path

from .errors import ConfigError, InputError


def credential_path():
    return Path.home() / ".config" / "typesafe-cli" / "credentials.json"


def restrict(path, directory=False):
    if os.name == "nt":
        import win32api
        import win32con
        import win32security

        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        finally:
            token.Close()
        acl = win32security.ACL()
        flags = 3 if directory else 0  # OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
        acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, flags, win32con.GENERIC_ALL, sid)
        win32security.SetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION
            | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None,
            None,
            acl,
            None,
        )
    else:
        path.chmod(0o700 if directory else 0o600)


def check_private(path):
    if path.is_symlink():
        raise ConfigError("Credential storage must not be a symbolic link.")
    if os.name != "nt":
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ConfigError("Credential storage must be owner-only; run auth login to repair it.")


def environment_key():
    return os.environ.get("TYPESAFE_API_KEY", "").strip()


def resolve():
    if key := environment_key():
        return key, "environment"
    path = credential_path()
    try:
        if not path.exists():
            return None, None
        check_private(path.parent)
        check_private(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        key = data.get("api_key") if isinstance(data, dict) else None
        if not isinstance(key, str) or not key.strip():
            raise ValueError
        return key.strip(), "file"
    except (OSError, ValueError):
        raise ConfigError(
            "Cannot read saved credentials; check permissions or run auth login."
        ) from None


def save(key):
    key = key.strip()
    if (
        not key
        or not key.isascii()
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in key)
    ):
        raise InputError("API key must contain printable ASCII characters without whitespace.")
    path = credential_path()
    temporary = None
    try:
        if path.parent.is_symlink() or path.is_symlink():
            raise ConfigError("Credential storage must not be a symbolic link.")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        restrict(path.parent, directory=True)
        fd, name = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            restrict(temporary)
            json.dump({"api_key": key}, output)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
    except ConfigError:
        raise
    except Exception:
        raise ConfigError(
            "Cannot save credentials; check configuration directory permissions."
        ) from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Preserve the sanitized write failure; temp file is already private.


def logout():
    try:
        credential_path().unlink(missing_ok=True)
    except OSError:
        raise ConfigError("Cannot remove saved credentials; check directory permissions.") from None
    return {
        "saved_credentials_removed": True,
        "environment_override_active": bool(environment_key()),
    }
