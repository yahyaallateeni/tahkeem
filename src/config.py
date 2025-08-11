import os

def get_secret_key() -> str:
    """Return SECRET_KEY from environment or raise a clear error."""
    try:
        return os.environ["SECRET_KEY"]
    except KeyError as e:
        raise RuntimeError("SECRET_KEY is not set in the environment.") from e
