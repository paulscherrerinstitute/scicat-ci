from functools import wraps
from logging import getLogger
from time import sleep
from urllib.error import URLError


def retry(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        for n in range(5):
            try:
                log.info(f"HTTP call attempt {n}")
                res = func(*args, **kwargs)
            except URLError as e:
                log.warning(e)
                if n == 4:
                    log.error(f"HTTP last call attempt failed")
                    return
                sleep(n * 10 or n)
            else:
                return res

    return wrap


log = getLogger("duo_sync")
