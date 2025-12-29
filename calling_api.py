import requests
import random
from database import connect_db, init
from datetime import datetime, timedelta
import pytz

def call_wiki_api(MM=12, DD=2, force_refresh=False):
    if not force_refresh:
        cached = get_cached(MM, DD)
        if cached:
            return cached
        
    wiki_link = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/{MM}/{DD}"
    headers = {
        "User-Agent": "BirthdayWisher/1.0 (contact@hasnat4763.me)"
    }
    try:
        result = requests.get(wiki_link, headers=headers)
        if result.status_code == 200:
            data = result.json()
            births = data.get("births", [])
            
            if births:
                cached_count = cache_birthday(MM, DD, births, clear_old=force_refresh)
                return get_cached(MM, DD)
            else:
                print("No births found for this date")
        else:
            print(f"Error: {result.status_code}")
    except Exception as e:
        print(f"Error calling Wiki API: {e}")

def cache_birthday(MM, DD, births, clear_old = False):
    try:
        db = connect_db()
        cursor = db.cursor()
        if clear_old:
            cursor.execute(
                '''
                DELETE FROM wiki_cache WHERE day = ? AND month = ?
                ''',
                (DD, MM)
            )
        cached_count = 0
        for person in births:
            name = person.get("text", "Unknown")
            year = person.get("year", "")
            pages = person.get("pages", [])
            description = ""
            if pages and len(pages) > 0:
                description = pages[0].get("extract", "")
                if not description:
                    description = pages[0].get("description", "")
            try:
                cursor.execute(
                    '''
                    INSERT OR IGNORE INTO wiki_cache (day, month, year, name, description)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (DD, MM, str(year), name, description)
                )
                if cursor.rowcount > 0:
                    cached_count += 1
            except Exception as e:
                print(f"Error caching {name}: {e}")
        db.commit()
        db.close()
        return cached_count

    except Exception as e:
        print(f"Error caching birthdays: {e}")
        return 0

def get_cached(MM, DD, max_age_days=30):
    try:
        db = connect_db()
        cursor = db.cursor()
        cutoff = datetime.now(pytz.utc) - timedelta(days=max_age_days)
        cursor.execute(
            """SELECT name, year, description, cached_at
            FROM wiki_cache
            WHERE day = ? AND month = ? and cached_at >= ?
            ORDER BY year DESC
            """,
            (DD, MM, cutoff.isoformat())
        )
        results = cursor.fetchall()
        db.close()
        
        if results:
            people = []
            for row in results:
                people.append({
                    "name": row[0],
                    "year": row[1],
                    "description": row[2],
                    "cached_at": row[3]
                    })
            return people

        return None
    except Exception as e:
        print(f"Error accessing cache: {e}")
        return None

def get_random_famous(MM, DD):
    people = call_wiki_api(MM, DD)
    if people and len(people) > 0:
        return random.choice(people)
    return None

def format_birthday(info):
    if not info:
        return ""
    
    name = info.get("name", "Unknown")
    year = info.get("year", "")
    description = info.get("description", "")

    message = f"\n\n🌟 *You share your birthday with {name}"
    
    if year: 
        message += f" (born {year})"
    
    message += "! *"
    
    if description:
        sentences = description.split('. ')
        desc_short = sentences[0]
        if len(desc_short) > 200:
            desc_short = desc_short[:197] + "..."
        elif not desc_short. endswith('.'):
            desc_short += "."
        
        message += f"\n_{desc_short}_"
    
    return message
def clean(days=90):
    try:
        db = connect_db()
        cursor = db.cursor()
        cutoff = datetime.now(pytz.utc) - timedelta(days=days)
        cursor.execute(
            '''
            DELETE FROM wiki_cache WHERE cached_at < ?
            ''',
            (cutoff.isoformat(),)
        )
        deleted_count = cursor.rowcount
        db.commit()
        db.close()
        return deleted_count
    except Exception as e:
        print(f"❌ Error cleaning cache: {e}")
        return 0
