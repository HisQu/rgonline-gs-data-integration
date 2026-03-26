import httpx
from pathlib import Path

URL = (
    "https://personendatenbank.germania-sacra.de/api/v1.0/person"
    "?query[0][field]=person.vorname&query[0][operator]=contains&query[0][value]=&query[0][connector]=and"
    "&query[1][field]=person.familienname&query[1][operator]=contains&query[1][value]=&query[1][connector]=and"
    "&query[2][field]=amt.bezeichnung&query[2][operator]=contains&query[2][value]=&query[2][connector]=and"
    "&query[3][field]=fundstelle.bandtitel&query[3][operator]=contains&query[3][value]=&format=turtle&limit=1000000"
)

OUTPUT = Path("data/raw/gs/persons.ttl")

def fetch():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", URL) as response:
        response.raise_for_status()
        with OUTPUT.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    print(f"Saved to {OUTPUT}")

if __name__ == "__main__":
    fetch()
