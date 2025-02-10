import argparse
import os
import shutil
import time
from douban2notion.notion_helper import NotionHelper


def move_and_rename_file():
    source_path = os.path.join("./OUT_FOLDER", "notion.svg")
    target_dir = os.path.join("./OUT_FOLDER", "movie")
    os.makedirs(target_dir, exist_ok=True)

    timestamp = int(time.time())
    new_filename = f"{timestamp}.svg"
    target_path = os.path.join(target_dir, new_filename)

    shutil.move(source_path, target_path)
    return target_path


def main():
    notion_helper = NotionHelper()
    image_file = move_and_rename_file()

    if image_file:
        repository = os.getenv("REPOSITORY")
        ref = os.getenv("REF", "main").split("/")[-1]
        image_url = f"https://raw.githubusercontent.com/{os.getenv('REPOSITORY')}/{os.getenv('REF').split('/')[-1]}/{image_file[2:]}"
        heatmap_url = f"https://heatmap.malinkang.com/?image={image_url}"

        if notion_helper.heatmap_block_id:
            response = notion_helper.update_heatmap(
                block_id=notion_helper.heatmap_block_id, url=heatmap_url
            )
            print(f"Heatmap updated successfully: {response}")
        else:
            print("Heatmap block ID not found in Notion.")


if __name__ == "__main__":
    main()
