import calendar
from datetime import datetime, timedelta
import hashlib
import os
import re
import requests
import base64
from douban2notion.config import (
    RICH_TEXT,
    URL,
    RELATION,
    NUMBER,
    DATE,
    FILES,
    STATUS,
    TITLE,
    SELECT,
    MULTI_SELECT
)
import pendulum

MAX_LENGTH = 1024  # NOTION 2000个字符限制 https://developers.notion.com/reference/request-limits

tz = "Asia/Shanghai"

def get_heading(level, content):
    heading = f"heading_{min(level, 3)}"
    return {
        "type": heading,
        heading: {
            "rich_text": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}],
            "color": "default",
            "is_toggleable": False,
        },
    }

def get_table_of_contents():
    return {"type": "table_of_contents", "table_of_contents": {"color": "default"}}

def get_title(content):
    return {"title": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}]}

def get_rich_text(content):
    return {"rich_text": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}]}

def get_url(url):
    return {"url": url}

def get_file(url):
    return {"files": [{"type": "external", "name": "Cover", "external": {"url": url}}]}

def get_multi_select(names):
    return {"multi_select": [{"name": name} for name in names]}

def get_relation(ids):
    return {"relation": [{"id": id} for id in ids]}

def get_date(start, end=None):
    return {"date": {"start": start, "end": end, "time_zone": tz}}

def get_icon(url):
    return {"type": "external", "external": {"url": url}}

def get_select(name):
    return {"select": {"name": name}}

def get_number(number):
    return {"number": number}

def get_quote(content):
    return {"type": "quote", "quote": {"rich_text": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}], "color": "default"}}

def get_callout(content, style, colorStyle, reviewId):
    emoji = {0: "💡", 1: "⭐", 2: "〰"}.get(style, "〰")
    if reviewId is not None:
        emoji = "✍️"
    color_map = {1: "red", 2: "purple", 3: "blue", 4: "green", 5: "yellow"}
    color = color_map.get(colorStyle, "default")
    return {"type": "callout", "callout": {"rich_text": [{"type": "text", "text": {"content": content[:MAX_LENGTH]}}], "icon": {"emoji": emoji}, "color": color}}

def format_time(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours}时" * (hours > 0) + f"{minutes}分" * (minutes > 0)

def format_date(date, fmt="%Y-%m-%d %H:%M:%S"):
    return date.strftime(fmt)

def timestamp_to_date(timestamp):
    return datetime.utcfromtimestamp(timestamp) + timedelta(hours=8)

def get_first_and_last_day_of_month(date):
    first_day = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = date.replace(day=calendar.monthrange(date.year, date.month)[1], hour=0, minute=0, second=0, microsecond=0)
    return first_day, last_day

def get_first_and_last_day_of_year(date):
    first_day = date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = date.replace(month=12, day=31, hour=0, minute=0, second=0, microsecond=0)
    return first_day, last_day

def get_first_and_last_day_of_week(date):
    first_day = (date - timedelta(days=date.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    last_day = first_day + timedelta(days=6)
    return first_day, last_day

def get_properties(data, type_map):
    properties = {}
    for key, value in data.items():
        if value is None:
            continue
        prop_type = type_map.get(key)
        if prop_type == TITLE:
            properties[key] = get_title(value)
        elif prop_type == RICH_TEXT:
            properties[key] = get_rich_text(value)
        elif prop_type == NUMBER:
            properties[key] = get_number(value)
        elif prop_type == STATUS:
            properties[key] = {"status": {"name": value}}
        elif prop_type == FILES:
            properties[key] = get_file(value)
        elif prop_type == DATE:
            properties[key] = get_date(pendulum.from_timestamp(value, tz=tz).to_datetime_string())
        elif prop_type == URL:
            properties[key] = get_url(value)
        elif prop_type == SELECT:
            properties[key] = get_select(value)
        elif prop_type == MULTI_SELECT:
            properties[key] = get_multi_select(value)
        elif prop_type == RELATION:
            properties[key] = get_relation(value)
    return properties

def get_property_value(prop):
    if prop is None:
        return None
    prop_type = prop.get("type")
    content = prop.get(prop_type)
    if not content:
        return None
    if prop_type in ["title", "rich_text"]:
        return content[0].get("plain_text") if content else None
    if prop_type in ["status", "select"]:
        return content.get("name")
    if prop_type == "files" and content:
        return content[0].get("external", {}).get("url")
    if prop_type == "date":
        return str_to_timestamp(content.get("start"))
    return content

def str_to_timestamp(date_str):
    if not date_str:
        return 0
    return int(pendulum.parse(date_str).timestamp())

def upload_image(folder_path, filename, file_path):
    with open(file_path, 'rb') as file:
        content_base64 = base64.b64encode(file.read()).decode('utf-8')
    data = {'file': content_base64, 'filename': filename, 'folder': folder_path}
    response = requests.post('https://wereadassets.malinkang.com/', json=data)
    if response.status_code == 200:
        print('File uploaded successfully.')
        return response.text
    print(f"Failed to upload file. Status code: {response.status_code}")
    return None

def url_to_md5(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def download_image(url, save_dir="cover"):
    os.makedirs(save_dir, exist_ok=True)
    file_name = f"{url_to_md5(url)}.jpg"
    save_path = os.path.join(save_dir, file_name)
    if os.path.exists(save_path):
        print(f"File {file_name} already exists. Skipping download.")
        return save_path
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
        print(f"Image downloaded successfully to {save_path}")
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
    return save_path

def upload_cover(url):
    cover_file = download_image(url)
    return upload_image("cover", os.path.basename(cover_file), cover_file)

def get_embed(url):
    return {"type": "embed", "embed": {"url": url}}
