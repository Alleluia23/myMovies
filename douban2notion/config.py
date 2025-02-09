RICH_TEXT = "rich_text"
URL = "url"
RELATION = "relation"
NUMBER = "number"
DATE = "date"
FILES = "files"
STATUS = "status"
TITLE = "title"
SELECT = "select"
MULTI_SELECT = "multi_select"

TAG_ICON_URL = "https://www.notion.so/icons/tag_gray.svg"
USER_ICON_URL = "https://www.notion.so/icons/user-circle-filled_gray.svg"

movie_properties_type_dict = {
    "电影名": TITLE,
    "短评": RICH_TEXT,
    "导演": RELATION,
    "演员": MULTI_SELECT,
    "封面": FILES,
    "分类": RELATION,
    "状态": STATUS,
    "类型": SELECT,
    "评分": SELECT,
    "日期": DATE,
    "简介": RICH_TEXT,
    "豆瓣链接": URL,
}
