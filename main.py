from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import time
import requests
import schedule
import threading
from datetime import datetime, timedelta
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import pytz
import logging
from logging.handlers import RotatingFileHandler
from database import init, connect_db
from calling_api import get_random_famous, format_birthday, clean
load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BIRTHDAY_CHANNEL = os.getenv("BIRTHDAY_CHANNEL_ID")
ADMIN = os.getenv("ADMIN_USER_ID")
ADMINS = [admin.strip() for admin in ADMIN.split(",")] if ADMIN else []
CANVAS_ID = os.getenv("CANVAS_FILE_ID")

assert APP_TOKEN, "APP_TOKEN has not been set"
assert BOT_TOKEN, "BOT_TOKEN has not been set"
assert BIRTHDAY_CHANNEL, "BIRTHDAY_CHANNEL_ID has not been set"
assert ADMIN, "ADMIN_USER_ID has not been set"
assert CANVAS_ID, "CANVAS_FILE_ID has not been set"

app = App(token=BOT_TOKEN)
client = WebClient(token=BOT_TOKEN)


init()

last_day_without_birthdays = None

logger = logging.getLogger("BirthdayWisherOrpheus")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    fh = RotatingFileHandler(
        "birthday_wisher_orpheus.log", maxBytes=5*1024*1024, encoding='utf-8', backupCount=3
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def log(e, level = "info", exc_info=False):
    if level == "info":
        logger.info(f"{e}", exc_info=exc_info)
    elif level == "warning":
        logger.warning(f"{e}", exc_info=exc_info)
    elif level == "error":
        logger.error(f"{e}", exc_info=exc_info)
    elif level == "debug":
        logger.debug(f"{e}", exc_info=exc_info)




@app.command("/birthday_test")
def handle_birthday_test(ack, body, respond):
    ack()
    
    user_id = body["user_id"]

    if user_id not in ADMINS:
        respond("This command is only available to administrators.")
        return
    text = body.get("text", "").strip()
    if text: 
        try:
            DD, MM = map(int, text.split("/"))
            test_day, test_month = DD, MM
        except:
            respond("Invalid format!  Use: `/birthday_test DD/MM` or leave empty for today")
            return
    else: 
        now = datetime.now()
        test_day, test_month = now.day, now.month
    
    db = connect_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT user_id, tz FROM birthday_info WHERE day = ? AND month = ? 
        ''', (test_day, test_month)
    )
    results = cursor.fetchall()
    db.close()
    
    if not results: 
        respond(f"No birthdays registered for {test_day}/{test_month}")
        return
    
    respond(f"Starting test for {test_day}/{test_month} birthdays...")

    thread_ts = None
    if BIRTHDAY_CHANNEL:
        today_str = datetime.now().strftime('%Y-%m-%d')
        thread_ts = get_or_create_daily_thread(today_str)
    
    sent_dm_count = 0
    sent_channel_count = 0
    
    for test_user_id, tz in results:
        try:
            famous_person = get_random_famous(test_month, test_day)
            famous_text = format_birthday(famous_person)
            dm_message = f"""🎉🎂 *Happy Birthday! * 🎈🎁 (TEST)

Wishing you an amazing day filled with joy, laughter, and wonderful memories! 

From your Slack team! 🥳{famous_text}"""
            
            app.client.chat_postMessage(
                channel=test_user_id,
                text=dm_message
            )
            sent_dm_count += 1
            log(f"✅ Test DM sent to {test_user_id}", level="info")
            if thread_ts:
                send_birthday_to_thread(test_user_id, famous_person, thread_ts)
                sent_channel_count += 1
                log(f"✅ Test channel post sent for {test_user_id}", level="info")
            
        except Exception as e: 
            log(f"❌ Error sending test wish to {test_user_id}:  {e}", level="error", exc_info=True)
    result_msg = f"*Test Complete!*\n\n"
    result_msg += f"Date tested: {test_day}/{test_month}\n"
    result_msg += f"DMs sent: {sent_dm_count}\n"
    
    if BIRTHDAY_CHANNEL:
        result_msg += f"Channel posts: {sent_channel_count}\n"
        if thread_ts:
            result_msg += f"Posted to thread in <#{BIRTHDAY_CHANNEL}>"
    else:
        result_msg += f"⚠️ Channel announcements disabled (BIRTHDAY_CHANNEL not set)"
    
    respond(result_msg)


@app.command("/birthday_register")
def handle_birthday_register(ack, body, respond):
    ack()
    print(body)
    user_id = body["user_id"]
    text = body["text"]
    if text == "":
        respond("Please provide your birthday in the format: `DD/MM` (e.g., `25/12` for December 25th)")
        return
    try:
        MM, DD = map(int, text.split("/"))
        if (DD > 31 or DD < 1) or (MM > 12 or MM < 1):
            respond("Invalid Date or Month Check Again.")
            return
        else:
            if MM == 2 and DD > 29:
                respond("Invalid Date February only has 29 days")
                return
            elif MM in [4, 6, 9, 11] and DD > 30:
                respond("Invalid Date this month has 30 days only")
                return
    except:
        respond("Invalid format!  Use: `/birthday_register DD/MM`")
        return            
    data = str(MM)+"/"+str(DD)
    try:
        add_users_to_db(user_id, {"birthday": data})
        respond("Your Birthday has been Registered Successfully!")
    except Exception as e:
        respond(f"There is a problem contact someone: {e}")
        log(f"Error occurred while registering birthday for {user_id}: {e}", level="error", exc_info=True)
    log(f"Registered birthday for {user_id}: {DD}/{MM}", level="info")

@app.command("/birthday_check")
def handle_birthday_check(ack, body, respond):
    ack()
    user_id = body["user_id"]
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            '''
            SELECT day, month, tz FROM birthday_info WHERE user_id = ?
            ''', (user_id,)
            )
        result = cursor.fetchone()
        db.close()
        log(f"Birthday check for {user_id}: {result}", level="info")
        if result:
            dd, mm, tz = result
            respond(f"You set your birthday as: {dd}/{mm} (Timezone: {tz})")
        else:
            respond("Your data doesn't exist yet.")
    except Exception as e:
        log(f"Error occurred while checking birthday for {user_id}: {e}", level="error", exc_info=True)
        respond("There is a problem contact someone")
        return

@app.command("/birthday_list")
def handle_birthday_list(ack, body, respond):
    ack()
    user_id = body["user_id"]
    users = 0

    if user_id not in ADMINS:
        respond("This command is only available to administrators.")
        return

    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT user_id, day, month, tz
            FROM birthday_info
            ORDER BY month ASC, day ASC
            """
        )
        rows = cursor.fetchall()
        db.close()

        if not rows:
            respond("No birthdays are registered yet.")
            return

        lines = ["*Registered birthdays (sorted):*"]
        for uid, day, month, tz in rows:
            tz_display = tz if tz else "Unknown"
            users += 1
            lines.append(f"• <@{uid}> — {day:02d}/{month:02d} — `{tz_display}`")

        lines.append(f"\nTotal users with birthdays: {users}")
        
        respond("\n".join(lines))

    except Exception as e:
        log(f"{e}", level="error", exc_info=True)
        respond("There was a problem fetching the birthday list: " + str(e))


@app.command("/birthday_delete")
def handle_birthday_delete(ack, body):
    ack()
    user_id = body["user_id"]
    app.client.chat_postMessage(
        channel=user_id,
        text="Are you sure you want to delete your birthday data?",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Are you sure?"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Yes, Delete it"
                        },
                        "style": "danger",
                        "action_id": "confirm_delete"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "No"
                        },
                        "style": "primary",
                        "action_id": "cancel_delete"
                    }
                ]
            }
        ]
    )
    
    
@app.action("confirm_delete")
def handle_confirm_delete(ack, body, client, logger):
    ack()
    logger.info(body)
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]
    ts = body["message"]["ts"]
    client.chat_update(channel=channel_id, ts=ts, text="Deleting your birthday data...")
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
        """
        DELETE FROM birthday_info WHERE user_id = ?
        """, (user_id,)
        )
        db.commit()
        db.close()
    except Exception as e:
        client.chat_postMessage(channel=channel_id, text="There was a problem deleting your data." + str(e))
        log(f"Error occurred while deleting birthday data for {user_id}: {e}", level="error", exc_info=True)

@app.action("cancel_delete")
def handle_cancel_delete(ack, body, client, logger):
    ack()
    logger.info(body)
    channel_id = body["channel"]["id"]
    ts = body["message"]["ts"]
    client.chat_update(channel=channel_id, ts=ts, text="Ok not deleting anything.")


@app.command("/birthday_sync_with_canvas")
def handle_slack_canvas(ack, body, respond):
    ack()
    user_id = body["user_id"]
    synced_users = []
    success = 0
    if user_id not in ADMINS:
        respond("This command is only available to administrators.")
        return
    
    response = get_canvas_content(CANVAS_ID)
    if response:
        parsed = parse_canvas_content(response)
        for uid, data in parsed.items():
            add_users_to_db(uid, data)
            synced_users.append(uid)
        success = len(synced_users)
    respond(f"Sync complete! Successfully synced {success} users. Synced users: {', '.join(synced_users)}")

@app.error
def global_error_handler(error, body, logger):
    logger.exception("Unhandled Slack error: %s | body=%s", error, body)

def add_users_to_db(uid, data):
    user_id = uid.strip("<>@|")
    text = data.get("birthday", "")
    user_tz = None  
    userinfo = None
    
    if len(text.split("/")) == 3:
        MM,DD, L = text.split("/")
        MM, DD = map(int, (DD, MM))
    elif len(text.split("/")) == 2:
        MM,DD = map(int, text.split("/"))
    else:
        log(f"Invalid birthday format for {user_id}: {text}", level="error")
        return
    if (DD > 31 or DD < 1) or (MM > 12 or MM < 1):
        log(f"Invalid date for {user_id}: {text}", level="error")
        return
    else:
        if MM == 2 and DD > 29:
            log(f"Invalid date for {user_id}: {text}", level="error")
            return
        elif MM in [4, 6, 9, 11] and DD > 30:
            log(f"Invalid date for {user_id}: {text}", level="error")
            return
    try:
        userinfo = client.users_info(user=user_id)
    except Exception as e:
        log(f"Error fetching user info for {user_id}: {e}", level="error")
        return
      
    if userinfo and userinfo.get("ok") and userinfo.get("user"):
        user_obj = userinfo.get("user")
        user_tz = user_obj.get("tz") if user_obj else None
    else:
        log(f"Could not fetch user info for {user_id}. Skipping.", level="error")
    
    if not user_tz:
        user_tz = "UTC"
        log(f"No timezone found for {user_id}, defaulting to UTC", level="warning")
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
                """
                INSERT OR REPLACE INTO birthday_info (user_id, day, month, tz)
                VALUES (?,?,?,?)
                """, (user_id, DD, MM, user_tz)
            )
        db.commit()
        db.close()
    except Exception as e:
        log(f"{e}", level="error", exc_info=True)
    
    log(f"Registered birthday for {user_id}: {MM}/{DD}", level="info")


def get_canvas_content(canvas_id):
    file_response = app.client.files_info(file=canvas_id)
    file_obj = file_response.get("file", {})
    
    download_url = file_obj.get("url_private_download")
    if not download_url:
        log("No download URL found", level="error")
        return None
    headers = {"Authorization": f"Bearer {BOT_TOKEN}"}
    response = requests.get(download_url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        log(f"Download failed: {response.status_code}", level="error")
        return None

def parse_canvas_content(content: str) -> dict[str, str]:
    soup = BeautifulSoup(content, "html.parser")
    birthdays = {}

    for li in soup.find_all("li"):
        a_tag = li.find("a")
        if not a_tag:
            continue

        user_id = a_tag.get_text(strip=True).lstrip("@")

        full_text = li.get_text(separator=" ", strip=True)

        birthday_separated = full_text.split(":", 1)[-1].strip() if ":" in full_text else ""
        
        birthdays[user_id] = {
            "birthday": birthday_separated,
        }

    return birthdays
    

def get_or_create_daily_thread(date_str):
    db = None
    if not BIRTHDAY_CHANNEL:
        return None
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT thread_ts FROM birthday_threads WHERE date = ?  AND channel_id = ?",
            (date_str, BIRTHDAY_CHANNEL)
        )
        result = cursor.fetchone()
        
        if result:
            thread_ts = result[0]
            log(f"✅ Using existing thread for {date_str}", level="info")
        else:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%B %d, %Y')  # e.g., "December 29, 2025"
            
            response = app.client.chat_postMessage(
                channel=BIRTHDAY_CHANNEL,
                text=f"🎉🎂 *Birthdays Today - {formatted_date}* 🎈🎁",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🎉 Birthdays Today - {formatted_date}",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Happy birthday to our amazing Hack Clubbers! 🥳\n_Check the thread below for individual wishes_ 👇"
                        }
                    }
                ]
            )
            
            thread_ts = response['ts']
            cursor.execute(
                """
                INSERT INTO birthday_threads (date, channel_id, thread_ts)
                VALUES (?, ?, ?)
                """,
                (date_str, BIRTHDAY_CHANNEL, thread_ts)
            )
            db.commit()
            log(f"✅ Created new thread for {date_str}", level="info")
        
        db.close()
        return thread_ts
        
    except Exception as e:
        log(f"{e}", level="error", exc_info=True)
        if db:
            db.close()
        return None

def log_wished(user_id, year, month, day, status=True):
    db = None
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
    """INSERT OR REPLACE INTO birthday_log (user_id, year, month, day, status, time)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        (user_id, year, month, day, status)
        )
        db.commit()
        db.close()
        return True
    except Exception as e:
        log(f"{e}", level="error", exc_info=True)
        if db:
            db.close()
        return False

def check_if_wished(user_id, year, month, day):
    try:
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            '''
            SELECT status FROM birthday_log
            WHERE user_id = ? AND year = ? AND month = ? AND day = ?
            ''',
            (user_id, year, month, day)
        )
        result = cursor.fetchone()
        db.close()
        return bool(result and result[0])
    except Exception as e:
        log(f"{e}", level="error", exc_info=True)
        return False

def send_birthday_to_thread(user_id, famous_person, thread_ts):
    if not BIRTHDAY_CHANNEL or not thread_ts:
        return
    
    try:
        famous_text = ""
        if famous_person: 
            name = famous_person.get("name", "Unknown")
            year = famous_person.get("year", "")
            description = famous_person.get("description", "")
            
            famous_text = f"\n\n🌟 *You share your birthday with {name}"
            if year:
                famous_text += f" (born {year})"
            famous_text += "! *"
            
            if description: 
                sentences = description.split('. ')
                desc_short = sentences[0]
                if len(desc_short) > 200:
                    desc_short = desc_short[:197] + "..."
                elif not desc_short.endswith('.'):
                    desc_short += "."
                famous_text += f"\n_{desc_short}_"
        message = f"""🎂 Happy Birthday <@{user_id}>!  🎉

Wishing you an amazing day filled with joy, laughter, and wonderful memories!{famous_text}"""
        
        app.client.chat_postMessage(
            channel=BIRTHDAY_CHANNEL,
            thread_ts=thread_ts,
            text=message
        )
        log(f"✅ Posted birthday wish for {user_id} in thread", level="info")
        
    except Exception as e:
        log(f"{e}", level="error", exc_info=True)


def find_and_send_wishes():
    global last_day_without_birthdays
    now = datetime.now(pytz.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    
    log(f"\n🔍 Birthday check at {now.strftime('%Y-%m-%d %H:%M')} UTC", level="info")
    
    db = connect_db()
    cursor = db.cursor()
    
    cursor.execute(
        '''
        SELECT user_id, day, month, tz FROM birthday_info WHERE
        (day = ? AND month = ?) OR
        (day = ? AND month = ?) OR
        (day = ? AND month = ?)
        ''', 
        (yesterday.day, yesterday.month,
         today.day, today.month,
         tomorrow.day, tomorrow.month)
    )
    results = cursor.fetchall()
    db.close()
    
    log(f"Checking {len(results)} user(s)", level="info")
    thread_ts = None

    if BIRTHDAY_CHANNEL and results: 
        today_str = today.strftime('%Y-%m-%d')
        thread_ts = get_or_create_daily_thread(today_str)
    
    for (user_id, day, month, tz) in results:
        try:
            if tz:
                try: 
                    user_timezone = pytz. timezone(tz)
                    user_now = datetime.now(user_timezone)
                except pytz.UnknownTimeZoneError:
                    log(f"⚠️ Unknown timezone '{tz}' for {user_id}", level="error")
                    user_now = datetime.now(pytz.utc)
            else:
                user_now = datetime.now(pytz.utc)
            if user_now.day == day and user_now.month == month:
                if not check_if_wished(user_id, user_now.year, month, day):
                    wish_success = False
                    try:
                        famous_person = get_random_famous(month, day)
                        famous_text = format_birthday(famous_person)
                        dm_message = f"""🎉🎂 *Happy Birthday! * 🎈🎁
Wishing you an amazing day filled with joy, laughter, and wonderful memories! 
🥳{famous_text}"""
                        
                        app.client.chat_postMessage(
                            channel=user_id,
                            text=dm_message
                        )
                        log(f"✅ Sent DM to {user_id}", level="info")
                        
                        if thread_ts:  
                            send_birthday_to_thread(user_id, famous_person, thread_ts)
                        
                        wish_success = True
                        
                    except Exception as send_error: 
                        log(f"Error sending wish to {user_id}: {send_error}", level="error", exc_info=True)
                        wish_success = False
                    
                    finally: 
                        log_result = log_wished(user_id, user_now.year, month, day, status=wish_success)
                        if not log_result:
                            log(f"⚠️ Warning: Failed to log wish for {user_id}", level='warning')
                else:
                    log(f"⏭️ Already wished {user_id} on {day}/{month}/{user_now.year}, skipping", level="info")

        except Exception as e:
            log(f"❌ Error processing {user_id}: {e}", level="error", exc_info=True)

    if last_day_without_birthdays != today:
        last_day_without_birthdays = today
        db = connect_db()
        cursor = db.cursor()
        cursor.execute(
            '''SELECT COUNT(*) FROM birthday_info WHERE day = ? AND month = ?'''
            ,(today.day, today.month)
        )
        count = cursor.fetchone()[0]
        db.close()
        if count == 0:
            run_birthday_not_celebrated_streak(celebrated_today=False)
        else:
            run_birthday_not_celebrated_streak(celebrated_today=True)
    
def daily_cleanup():
    log(f"\nRunning daily cache cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M')}", level="info")
    deleted = clean(days=90)
    log(f"Cleaned {deleted} old entries", level="info")



def run_birthday_not_celebrated_streak(celebrated_today):
    db = connect_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT streak FROM birthday_not_celebrated_streak
        '''
    )
    result = cursor.fetchone()
    current_streak = result[0] if result else 0
    if BIRTHDAY_CHANNEL:
        if celebrated_today:
            current_streak = 0
            streak_message = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*STREAK DEACTIVATED*!"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "image",
                            "image_url": "https://api.slack.com/img/blocks/bkb_template_images/notificationsWarningIcon.png",
                            "alt_text": "notifications warning icon"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"Today is *{datetime.now().strftime('%d %B, %Y')}*"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "The Streak has been reset to 0 because a birthday has been/will be celebrated today"
                    }
                }
            ]
            
        else:
            current_streak = result[0] if result else 0
            if current_streak == 0:
                current_streak = 1
                streak_message = birthday_celebration_streak_message_builder(datetime.now().strftime('%d %B, %Y'), current_streak)
            else:
                current_streak += 1
                streak_message = birthday_celebration_streak_message_builder(datetime.now().strftime('%d %B, %Y'), current_streak)
    
        app.client.chat_postMessage(channel=BIRTHDAY_CHANNEL, blocks=streak_message)
    
            
    cursor.execute(
        '''
        INSERT OR REPLACE INTO birthday_not_celebrated_streak (id, streak)
        VALUES (1, ?)
        ''', 
        (current_streak,))
    db.commit()
    db.close()


def birthday_celebration_streak_message_builder(date, streak):
    return [
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": "*STREAK ACTIVATED*!"
			}
		},
		{
			"type": "divider"
		},
		{
			"type": "context",
			"elements": [
				{
					"type": "image",
					"image_url": "https://api.slack.com/img/blocks/bkb_template_images/notificationsWarningIcon.png",
					"alt_text": "notifications warning icon"
				},
				{
					"type": "mrkdwn",
					"text": f"Today is *{date}*"
				}
			]
		},
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"Because no birthdays were celebrated today so the streak has been brought up to {streak}"
			}
		}
	]

def monthly_birthdays():
    date = datetime.now().date()
    month = None
    users = 0
    if date.day == 1 or date.day == 15:
        month = datetime.now().month
    else:
        return

    db = connect_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT user_id, day, month FROM birthday_info WHERE month = ?
        ''', (month,)
    )
    results = cursor.fetchall()
    cursor.close()
    db.close()
    if not results:
        return
    birthdays_in_month = len(results)
    birthday_list_message = f"🎉 Birthdays this month: {birthdays_in_month} 🎂 \n They have birthdays on this month:\n"
    for uid, day, month in results:
        birthday_list_message += f"• <@{uid}> - {day}/{month}\n"
        users+=1
    
    birthday_list_message += f"\nTotal users with birthdays this month: {users}"

    if BIRTHDAY_CHANNEL:
        app.client.chat_postMessage(
            channel=BIRTHDAY_CHANNEL,
            text=birthday_list_message
        )

schedule.every().day.at("03:00").do(daily_cleanup)
schedule.every().hour.do(find_and_send_wishes)
schedule.every().day.at("00:00").do(monthly_birthdays)


def run_scheduler():
    log("\nScheduler started!")
    log("  Birthday checks:  Every hour")
    log("  Cache cleanup: Daily at 03:00 UTC")
    log("  Thread cleanup: Daily at 03:00 UTC")
    while True:
        schedule.run_pending()
        time.sleep(60)
    
threading.Thread(target=run_scheduler, daemon=True).start()


if __name__ == "__main__":
    socketmodehandler =SocketModeHandler(app, APP_TOKEN)
    socketmodehandler.start()