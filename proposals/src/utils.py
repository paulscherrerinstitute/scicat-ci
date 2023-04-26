from functools import wraps
from time import sleep
from urllib.error import URLError


def retry(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        for n in range(5):
            try:
                res = func(*args, **kwargs)
            except URLError:
                sleep(n * 10 or n)
            else:
                return res

    return wrap
