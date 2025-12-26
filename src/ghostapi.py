import jwt
import requests
from datetime import datetime
import time
import logging
from pathlib import Path
from instagram import Instagram
from db import Database
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GhostAPI:
    def __init__(self, base_url, admin_api_key):
        self.base_url = base_url.rstrip('/')
        self.key_id, self.key_secret = admin_api_key.split(':')
    
    def _generate_token(self):
        """Generate JWT token for authentication"""
        iat = int(datetime.now().timestamp())
        
        header = {
            'alg': 'HS256',
            'typ': 'JWT',
            'kid': self.key_id
        }
        
        payload = {
            'iat': iat,
            'exp': iat + 5 * 60,  # Token expires in 5 minutes
            'aud': '/admin/'
        }
        
        token = jwt.encode(
            payload,
            bytes.fromhex(self.key_secret),
            algorithm='HS256',
            headers=header
        )
        
        return token
    
    def _get_headers(self):
        """Get headers with fresh JWT token"""
        token = self._generate_token()
        return {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json',
            'Accept-Version': 'v5.0'  # Ghost API version
        }
    
    def create_post(self, title: str, content: str = None, mobiledoc: dict = None, status: str = 'published', tags: list[str] | None = None, **kwargs):
        """Create a post in Ghost"""
        url = f'{self.base_url}/ghost/api/admin/posts/'
        
        tag_list = []
        if tags:
            for tag in tags:
                tag_list.append({'name': tag})
        
        post_data = {
            'posts': [
                {
                    'title': title,
                    'status': status,
                    'tags': tag_list,
                    **kwargs
                }
            ]
        }
        
        # Add content in the appropriate format
        if mobiledoc:
            # Convert mobiledoc dict to JSON string
            post_data['posts'][0]['mobiledoc'] = json.dumps(mobiledoc)
        elif content:
            post_data['posts'][0]['html'] = content
        
        try:
            response = requests.post(
                url,
                json=post_data,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result['posts'][0] if result.get('posts') else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating post: {e}")
            if hasattr(e, 'response') and getattr(e.response, 'text', None):
                logger.error(f"Response: {e.response.text}")
            return None
    
    def upload_image(self, image_path):
        """Upload an image"""
        url = f'{self.base_url}/ghost/api/admin/images/upload/'
        
        token = self._generate_token()
        headers = {
            'Authorization': f'Ghost {token}',
            'Accept-Version': 'v5.0'
        }
        
        try:
            # Determine MIME type based on file extension
            path = Path(image_path)
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            mime_type = mime_types.get(path.suffix.lower(), 'image/jpeg')
            
            with open(image_path, 'rb') as f:
                files = {
                    'file': (path.name, f, mime_type)
                }
                response = requests.post(url, files=files, headers=headers, timeout=120)
                response.raise_for_status()
                result = response.json()
                return result['images'][0]['url']
        except requests.exceptions.RequestException as e:
            logger.error(f"Error uploading image {image_path}: {e}")
            return None

    def upload_media(self, media_path: str) -> str | None:
        """
        Upload a media file (e.g., video) to Ghost Admin Media API and return its URL.
        """
        url = f'{self.base_url}/ghost/api/admin/media/upload/'

        token = self._generate_token()
        headers = {
            'Authorization': f'Ghost {token}',
            'Accept-Version': 'v5.0'
        }

        try:
            # Determine MIME type based on file extension
            path = Path(media_path)
            mime_types = {
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
                '.ogg': 'video/ogg'
            }
            mime_type = mime_types.get(path.suffix.lower(), 'video/mp4')
            
            with open(media_path, 'rb') as f:
                files = {
                    'file': (path.name, f, mime_type)
                }
                resp = requests.post(url, files=files, headers=headers, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                return data['media'][0]['url']
        except requests.exceptions.RequestException as e:
            logger.error(f"Error uploading media {media_path}: {e}")
            if hasattr(e, 'response') and getattr(e.response, 'text', None):
                logger.error(f"Response: {e.response.text}")
            return None

    def create_media_post(
        self,
        title: str,
        image_paths: list[str] | None = None,
        video_paths: list[str] | None = None,
        video_urls: list[str] | None = None,
        description: str | None = None,
        status: str = 'published',
        tags: list[str] | None = None,
        **kwargs
    ):
        """
        Create a post that contains multiple photos and videos.

        image_paths: local image file paths to upload to Ghost
        video_paths: local video file paths to upload via Admin Media API
        video_urls: externally hosted video URLs to embed
        """
        image_paths = image_paths or []
        video_paths = video_paths or []
        video_urls = video_urls or []

        logger.info(f"Creating Ghost post: {title}")
        logger.info(f"Uploading {len(image_paths)} images and {len(video_paths)} videos")

        # 1) Upload images
        image_urls: list[str] = []
        for path in image_paths:
            logger.info(f"Uploading image: {path}")
            url = self.upload_image(path)
            if url:
                image_urls.append(url)
                logger.info(f"✓ Image uploaded: {url}")
            else:
                logger.warning(f"✗ Failed to upload image: {path}")

        # 2) Upload videos via media/upload and collect URLs
        uploaded_video_urls: list[str] = []
        for path in video_paths:
            logger.info(f"Uploading video: {path}")
            vurl = self.upload_media(path)
            if vurl:
                logger.info(vurl)
                uploaded_video_urls.append(vurl)
                logger.info(f"✓ Video uploaded: {vurl}")
            else:
                logger.warning(f"✗ Failed to upload video: {path}")

        all_video_urls = video_urls + uploaded_video_urls

        # 3) Build Mobiledoc content
        cards = []
        
        # Add description as markdown card
        if description:
            cards.append([
                "markdown",
                {
                    "markdown": description
                }
            ])
        
        # Add images as image cards
        for url in image_urls:
            cards.append([
                "image",
                {
                    "src": url,
                    "alt": "",
                    "cardWidth": "wide"
                }
            ])
        
        # Add videos as HTML cards (more compatibile per la resa)
        for vurl in all_video_urls:
            cards.append([
                "html",
                {
                    "html": (
                        '<figure class="kg-card kg-video-card kg-width-wide">'
                        f'  <video controls preload="metadata" src="{vurl}" style="width:100%;height:auto;"></video>'
                        '</figure>'
                    )
                }
            ])
        
        # Create Mobiledoc structure
        mobiledoc = {
            "version": "0.3.1",
            "atoms": [],
            "cards": cards,
            "markups": [],
            "sections": [[10, 0]] * len(cards)  # Reference each card
        }
        
        # Update sections to reference cards correctly
        mobiledoc["sections"] = [[10, i] for i in range(len(cards))]

        # 4) Create the post
        logger.info("Creating Ghost post...")
        ghost_post = self.create_post(
            title=title,
            mobiledoc=mobiledoc,
            status=status,
            tags=tags,
            **kwargs
        )
        
        if ghost_post:
            logger.info(f"✓ Ghost post created: {ghost_post.get('title')} ({ghost_post.get('url')})")
        else:
            logger.error(f"✗ Failed to create Ghost post: {title}")
        
        return ghost_post


def main():
    """Check Instagram for new posts and publish them on Ghost."""
    # Configuration
    GHOST_URL = ''
    ADMIN_API_KEY = ''  # Format: key_id:key_secret
    
    # Initialize Ghost API
    ghost = GhostAPI(GHOST_URL, ADMIN_API_KEY)
    
    # Initialize database and Instagram
    db = Database("instagram_posts.db")
    instagram = Instagram("la_terna_sinistrorsa", db)
    
    try:
        logger.info("Checking for new Instagram posts from @la_terna_sinistrorsa...")
        new_posts = instagram.download_new_posts()
        
        if not new_posts:
            logger.info("No new posts found")
            return
        
        logger.info(f"Found {len(new_posts)} new post(s)")
        
        for post in new_posts:
            logger.info(f"Processing post: {post['shortcode']}")
            
            # Get media files from the shortcode folder
            post_folder = Path(post['shortcode'])
            
            if post_folder.exists():
                # Collect all media files
                image_paths = [str(p) for p in sorted(post_folder.glob('*.jpg'))]
                video_paths = [str(p) for p in sorted(post_folder.glob('*.mp4'))]
                
                logger.info(f"Found {len(image_paths)} image(s) and {len(video_paths)} video(s)")
                
                # Create Ghost post with media files
                ghost_post = ghost.create_media_post(
                    #use the first 25 characters of the description as title, or shortcode if no description
                    title=f"{(post['description'][:30]+"...") if post['description'] else f'instagram post {datetime.now().strftime('%Y-%m-%d %H:%M')}'}",
                    image_paths=image_paths,
                    video_paths=video_paths,
                    description=post['description'],
                    status='published',
                    tags=['instagram', 'social-media']
                )
                
                if ghost_post:
                    logger.info(f"✓ Created Ghost post: {ghost_post.get('title')} ({ghost_post.get('url')})")
                else:
                    logger.error(f"✗ Failed to create Ghost post for {post['shortcode']}")
                
                # Delete folder after posting
                for file in post_folder.iterdir():
                    file.unlink()
                post_folder.rmdir()
                logger.info(f"Deleted folder {post_folder}")
            else:
                logger.warning(f"Post folder {post_folder} does not exist")
                
    except Exception as e:
        logger.error(f"Error checking and posting new posts: {e}")


if __name__ == '__main__':
    main()
