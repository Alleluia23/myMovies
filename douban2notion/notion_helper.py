import logging
import os
import re

from notion_client import Client
from retrying import retry

from douban2notion.utils import (
    format_date,
    get_date,
    get_first_and_last_day_of_month,
    get_first_and_last_day_of_week,
    get_first_and_last_day_of_year,
    get_icon,
    get_relation,
    get_title,
)

TAG_ICON_URL = "https://www.notion.so/icons/tag_gray.svg"
USER_ICON_URL = "https://www.notion.so/icons/user-circle-filled_gray.svg"
TARGET_ICON_URL = "https://www.notion.so/icons/target_red.svg"
BOOKMARK_ICON_URL = "https://www.notion.so/icons/bookmark_gray.svg"


class NotionHelper:
    database_name_dict = {
        "MOVIE_DATABASE_NAME": "电影",
        "DAY_DATABASE_NAME": "日",
        "WEEK_DATABASE_NAME": "周",
        "MONTH_DATABASE_NAME": "月",
        "YEAR_DATABASE_NAME": "年",
        "CATEGORY_DATABASE_NAME": "分类",
        "DIRECTOR_DATABASE_NAME": "导演",
    }
    database_id_dict = {}
    image_dict = {}

    def __init__(self):
        notion_token = os.getenv("NOTION_TOKEN") or os.getenv("MOVIE_NOTION_TOKEN")
        page_url = os.getenv("NOTION_MOVIE_URL")

        self.client = Client(auth=notion_token, log_level=logging.ERROR)
        self.__cache = {}
        self.page_id = self.extract_page_id(page_url)
        self.search_database(self.page_id)

        for key in self.database_name_dict.keys():
            if os.getenv(key):
                self.database_name_dict[key] = os.getenv(key)

        self.movie_database_id = self.database_id_dict.get(
            self.database_name_dict.get("MOVIE_DATABASE_NAME")
        )
        self.day_database_id = self.database_id_dict.get(
            self.database_name_dict.get("DAY_DATABASE_NAME")
        )
        self.week_database_id = self.database_id_dict.get(
            self.database_name_dict.get("WEEK_DATABASE_NAME")
        )
        self.month_database_id = self.database_id_dict.get(
            self.database_name_dict.get("MONTH_DATABASE_NAME")
        )
        self.year_database_id = self.database_id_dict.get(
            self.database_name_dict.get("YEAR_DATABASE_NAME")
        )
        self.category_database_id = self.database_id_dict.get(
            self.database_name_dict.get("CATEGORY_DATABASE_NAME")
        )
        self.director_database_id = self.database_id_dict.get(
            self.database_name_dict.get("DIRECTOR_DATABASE_NAME")
        )

        if self.day_database_id:
            self.write_database_id(self.day_database_id)
            
        self.test_get_blocks()


    def write_database_id(self, database_id):
        env_file = os.getenv('GITHUB_ENV')
        with open(env_file, "a") as file:
            file.write(f"DATABASE_ID={database_id}\n")
        print(f"Written DATABASE_ID: {database_id}")  # 添加调试信息


    def extract_page_id(self, notion_url):
        match = re.search(
            r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
            notion_url,
        )
        if match:
            return match.group(0)
        else:
            raise Exception(f"获取NotionID失败，请检查输入的Url是否正确")

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def search_database(self, block_id):
        children = self.client.blocks.children.list(block_id=block_id)["results"]
        for child in children:
            if child["type"] == "child_database":
                self.database_id_dict[
                    child.get("child_database").get("title")
                ] = child.get("id")
            elif child["type"] == "embed" and child.get("embed").get("url"):
                if child.get("embed").get("url").startswith("https://heatmap.malinkang.com/"):
                    self.heatmap_block_id = child.get("id")
            if "has_children" in child and child["has_children"]:
                self.search_database(child["id"])

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_heatmap(self, block_id, url):
        return self.client.blocks.update(block_id=block_id, embed={"url": url})

    def get_week_relation_id(self, date):
        year = date.isocalendar().year
        week = date.isocalendar().week
        week_name = f"{year}年第{week}周"
        start, end = get_first_and_last_day_of_week(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(week_name, self.week_database_id, TARGET_ICON_URL, properties)

    def get_month_relation_id(self, date):
        month_name = date.strftime("%Y年%-m月")
        start, end = get_first_and_last_day_of_month(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(month_name, self.month_database_id, TARGET_ICON_URL, properties)

    def get_year_relation_id(self, date):
        year_name = date.strftime("%Y")
        start, end = get_first_and_last_day_of_year(date)
        properties = {"日期": get_date(format_date(start), format_date(end))}
        return self.get_relation_id(year_name, self.year_database_id, TARGET_ICON_URL, properties)

    def get_day_relation_id(self, date):
        new_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_name = new_date.strftime("%Y年%m月%d日")
        properties = {"日期": get_date(format_date(date))}
        properties["年"] = get_relation([self.get_year_relation_id(new_date)])
        properties["月"] = get_relation([self.get_month_relation_id(new_date)])
        properties["周"] = get_relation([self.get_week_relation_id(new_date)])
        return self.get_relation_id(day_name, self.day_database_id, TARGET_ICON_URL, properties)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_relation_id(self, name, database_id, icon, properties={}):
        key = f"{database_id}{name}"
        if key in self.__cache:
            return self.__cache[key]
        
        filter = {"property": "标题", "title": {"equals": name}}
        response = self.client.databases.query(database_id=database_id, filter=filter)
        
        if not response.get("results"):
            parent = {"database_id": database_id, "type": "database_id"}
            properties["标题"] = get_title(name)
            page_id = self.client.pages.create(parent=parent, properties=properties, icon=get_icon(icon)).get("id")
        else:
            page_id = response.get("results")[0].get("id")

        self.__cache[key] = page_id
        return page_id

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def update_page(self, page_id, properties):
        return self.client.pages.update(page_id=page_id, properties=properties)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def create_page(self, parent, properties, icon):
        return self.client.pages.create(parent=parent, properties=properties, icon=icon)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query(self, **kwargs):
        kwargs = {k: v for k, v in kwargs.items() if v}
        return self.client.databases.query(**kwargs)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def query_all(self, database_id):
        results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            response = self.client.databases.query(
                database_id=database_id,
                start_cursor=start_cursor,
                page_size=100,
            )
            start_cursor = response.get("next_cursor")
            has_more = response.get("has_more")
            results.extend(response.get("results"))
        
        return results

    def get_date_relation(self, properties, date):
        properties["年"] = get_relation([self.get_year_relation_id(date)])
        properties["月"] = get_relation([self.get_month_relation_id(date)])
        properties["周"] = get_relation([self.get_week_relation_id(date)])
        properties["日"] = get_relation([self.get_day_relation_id(date)])

    def test_get_blocks(self):
        print(f"Testing block retrieval for page ID: {self.page_id}")
        try:
            children = self.client.blocks.children.list(block_id=self.page_id)["results"]
            for child in children:
                print(f"Block Type: {child['type']}, ID: {child.get('id')}, Title: {child.get('child_database', {}).get('title')}, Has Children: {child.get('has_children')}")
        except Exception as e:
            print(f"Error while retrieving blocks: {str(e)}")


