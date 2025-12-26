import instaloader
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                    logger.info(f"Downloading post: {shortcode}")
                    self.L.download_post(post, target=Path("media_downloads") / shortcode)
                    new_posts.append({
                        'shortcode': shortcode,
                        'description': post.caption
                    })
                    logger.info(f"Post {shortcode} downloaded to media_downloads/{shortcode}")
            
            if posts.total_index >= 5:
                break
                    
        return new_posts


#test code
if __name__ == "__main__":
    from db import Database

    db = Database("instagram_posts.db")
    instagram = Instagram("la_terna_sinistrorsa", db)
    new_posts = instagram.download_new_posts()
    for post in new_posts:
        db.insert_post(post['shortcode'], post['description'])
        print(f"Downloaded and saved post: {post['shortcode']}")