import instaloader
import os
from pathlib import Path

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
                    target_dir = Path("media_downloads") / shortcode
                    target_dir.mkdir(parents=True, exist_ok=True)
                    self.L.download_post(post, target=str(target_dir))
                    new_posts.append({
                        'shortcode': shortcode,
                        'description': post.caption
                    })
            if posts.total_index >=5:
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