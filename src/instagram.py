import instaloader
import os
from pathlib import Path
import shutil

print(os.getcwd())
class Instagram:
    def __init__(self, username: str, db):
        self.username = username
        self.db = db
        self.L = instaloader.Instaloader()

    def download_new_posts(self) -> dict:
        new_posts = []
        
        profile = instaloader.Profile.from_username(self.L.context, self.username)
        posts = profile.get_posts()
        for post in posts:
            if not post.is_pinned:
                shortcode = post.shortcode
                if not self.db.post_exists(shortcode):
                    # Create target directory
                    target_dir = Path("media_downloads") / shortcode
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Download to temp location
                    temp_dir = Path("temp_download")
                    self.L.download_post(post, target=str(temp_dir))
                    
                    # Move files from instaloader's subfolder to target
                    # instaloader creates: temp_download/username/media_files
                    instaloader_dir = temp_dir / self.username
                    if instaloader_dir.exists():
                        for file in instaloader_dir.iterdir():
                            if file.is_file() and file.suffix in ['.jpg', '.mp4']:
                                shutil.move(str(file), str(target_dir / file.name))
                        shutil.rmtree(temp_dir)
                    
                    new_posts.append({
                        'shortcode': shortcode,
                        'description': post.caption
                    })
            if posts.total_index >= 5:
                break
                    
        return new_posts        




#test code
if __name__ == "__main__":
    
    from db import Database

    db = Database("instagram_posts.db")
    instagram = Instagram("", db)
    new_posts = instagram.download_new_posts()
    for post in new_posts:
        db.insert_post(post['shortcode'], post['description'])
        print(f"Downloaded and saved post: {post['shortcode']}")