import json
import os
import pendulum
from retrying import retry
import requests
from douban2notion.notion_helper import NotionHelper
from douban2notion import utils
from douban2notion.config import movie_properties_type_dict, TAG_ICON_URL, USER_ICON_URL
from douban2notion.utils import get_icon
from dotenv import load_dotenv

load_dotenv()

DOUBAN_API_HOST = os.getenv("DOUBAN_API_HOST", "frodo.douban.com")
DOUBAN_API_KEY = os.getenv("DOUBAN_API_KEY", "0ac44ae016490db2204ce0a042db2916")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

headers = {
    "host": DOUBAN_API_HOST,
    "authorization": f"Bearer {AUTH_TOKEN}" if AUTH_TOKEN else "",
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.16(0x18001023) NetType/WIFI Language/zh_CN",
    "referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/84/page-frame.html",
}

rating = {
    1: "⭐️",
    2: "⭐️⭐️",
    3: "⭐️⭐️⭐️",
    4: "⭐️⭐️⭐️⭐️",
    5: "⭐️⭐️⭐️⭐️⭐️",
}

movie_status = {
    "mark": "想看",
    "doing": "在看",
    "done": "看过",
}

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def fetch_movies(user, status):
    offset = 0
    results = []
    url = f"https://{DOUBAN_API_HOST}/api/v2/user/{user}/interests"

    while True:
        params = {
            "type": "movie",
            "count": 50,
            "status": status,
            "start": offset,
            "apiKey": DOUBAN_API_KEY,
        }
        response = requests.get(url, headers=headers, params=params)

        if response.ok:
            data = response.json()
            interests = data.get("interests", [])
            if not interests:
                break
            results.extend(interests)
            offset += 50
        else:
            print(f"Failed to fetch data for status {status}: {response.status_code}")
            break
        
    if results:
        print(json.dumps(results[0], indent=4, ensure_ascii=False))

    return results


def sync_movies(douban_name, notion_helper):
    if not douban_name:
        print("Error: 请设置 DOUBAN_NAME 环境变量")
        return

    existing_movies = notion_helper.query_all(database_id=notion_helper.movie_database_id)
    movie_dict = {
        utils.get_property_value(item.get("properties").get("豆瓣链接")): {
            "短评": utils.get_property_value(item.get("properties").get("短评")),
            "状态": utils.get_property_value(item.get("properties").get("状态")),
            "日期": utils.get_property_value(item.get("properties").get("日期")),
            "评分": utils.get_property_value(item.get("properties").get("评分")),
            "page_id": item.get("id"),
            "分类": utils.get_property_value(item.get("properties").get("分类"))
        } for item in existing_movies
    }

    print(f"Found {len(movie_dict)} movies already in Notion")

    all_movies = []
    for status in movie_status.keys():
        fetched = fetch_movies(douban_name, status)
        print(f"Fetched {len(fetched)} movies with status '{movie_status[status]}'")
        all_movies.extend(fetched)

    for movie_entry in all_movies:
        subject = movie_entry.get("subject")
        if not subject:
            continue

        movie_data = {
            "电影名": subject.get("title"),
            "日期": pendulum.parse(movie_entry.get("create_time"), tz=utils.tz).replace(second=0).int_timestamp,
            "豆瓣链接": subject.get("url"),
            "状态": movie_status.get(movie_entry.get("status")),
            "评分": rating.get(movie_entry.get("rating", {}).get("value")),
            "短评": movie_entry.get("comment"),
            "分类": [
                notion_helper.get_relation_id(genre, notion_helper.category_database_id, TAG_ICON_URL)
                for genre in subject.get("genres", [])
            ]
        }

        existing_movie = movie_dict.get(movie_data["豆瓣链接"])

        if existing_movie:
            if any(
                existing_movie.get(key) != movie_data.get(key)
                for key in ["日期", "短评", "状态", "评分", "分类"]
            ):
                properties = utils.get_properties(movie_data, movie_properties_type_dict)
                properties["分类"] = {"relation": [{"id": rel_id} for rel_id in movie_data["分类"]]}
                notion_helper.get_date_relation(properties, pendulum.from_timestamp(movie_data["日期"]))
                notion_helper.update_page(page_id=existing_movie["page_id"], properties=properties)
        else:
            print(f"插入 {movie_data.get('电影名')}")
            cover = subject.get("pic", {}).get("normal", "").replace(".webp", ".jpg")
            movie_data["封面"] = cover
            movie_data["类型"] = subject.get("type")

            if subject.get("actors"):
                movie_data["演员"] = [actor.get("name") for actor in subject.get("actors", []) if actor.get("name")]
            if subject.get("directors"):
                movie_data["导演"] = [
                    notion_helper.get_relation_id(director.get("name"), notion_helper.director_database_id, USER_ICON_URL)
                    for director in subject.get("directors", [])
                ]

            properties = utils.get_properties(movie_data, movie_properties_type_dict)
            properties["分类"] = {"relation": [{"id": rel_id} for rel_id in movie_data["分类"]]}
            notion_helper.get_date_relation(properties, pendulum.from_timestamp(movie_data["日期"]))

            notion_helper.create_page(
                parent={"database_id": notion_helper.movie_database_id, "type": "database_id"},
                properties=properties,
                icon=get_icon(cover)
            )


def main():
    notion_helper = NotionHelper("movie")
    douban_name = os.getenv("DOUBAN_NAME")
    sync_movies(douban_name, notion_helper)


if __name__ == "__main__":
    main()
