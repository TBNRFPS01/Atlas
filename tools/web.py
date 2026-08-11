from urllib.request import urlopen


def fetch_url(url: str) -> str:
    with urlopen(url) as response:
        return response.read().decode("utf-8", errors="ignore")
