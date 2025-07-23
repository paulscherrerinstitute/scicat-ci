from functools import wraps
from logging import Logger, getLogger
from time import sleep
from urllib.error import URLError

log: Logger = getLogger("duo_sync")


def retry(func):
    """
    Decorator that retries a function up to 5 times if it raises a URLError.

    Args:
        func (Callable): The function to retry.

    Returns:
        Callable: A wrapped version of the function that will retry on URLError.
    """

    @wraps(func)
    def wrap(*args, **kwargs):
        for n in range(5):
            try:
                log.info(f"HTTP call attempt {n}")
                res = func(*args, **kwargs)
            except URLError as e:
                log.warning(e)
                if n == 4:
                    log.error("HTTP last call attempt failed")
                    return
                sleep(n * 10 or n)
            else:
                return res
        return None

    return wrap
