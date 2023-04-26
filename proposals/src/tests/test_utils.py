from urllib.error import URLError

from utils import retry


def test_retry():
    i = []

    def func(ilist):
        if len(ilist) == 0:
            ilist.append(1)
            raise URLError("")
        return len(ilist)

    assert retry(func)(i) == 1
