import requests
import random


def call_wiki_api(MM=12, DD=2):
    wiki_link = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/{MM}/{DD}"
    headers = {
        "User-Agent": "BirthdayWisher/1.0 (contact@hasnat4763.me)"
    }
    result = requests.get(wiki_link, headers=headers)
    if result.status_code == 200:
        data = result.json()
        births = data.get("births", [])
        
        if births:
            person = random.choice(births)
            name = person.get("text", "Unknown")
            print(f"Name: {name}")
        else:
            print("No births found for this date")
    else:
        print(f"Error: {result.status_code}")

        
if __name__ == "__main__":
    call_wiki_api(12, 2)