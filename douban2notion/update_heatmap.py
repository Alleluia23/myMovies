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
    return new_filename  # 返回文件名以便用于生成 URL


def main():
    notion_helper = NotionHelper()
    new_filename = move_and_rename_file()

    if new_filename:
        repository = os.getenv("REPOSITORY")
        username, repo_name = repository.split("/")
        
        # 生成 GitHub Pages URL
        image_url = f"https://{username}.github.io/{repo_name}/OUT_FOLDER/movie/{new_filename}"
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
