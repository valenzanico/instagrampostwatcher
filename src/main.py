import asyncio
import os
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from instagram import Instagram
from db import Database
import logging
from pathlib import Path
from ghostapi import GhostAPI
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Telegram bot token
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # Telegram channel ID
GHOST_URL = os.getenv("GHOST_URL")  # Ghost site URL
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
INSTAGRAM_PAGE = os.getenv("INSTAGRAM_PAGE")
DB_NAME = "instagram_posts.db"
# Telegram bot token and channel ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db = Database(DB_NAME)
instagram = Instagram(INSTAGRAM_PAGE, db)
ghost = GhostAPI(GHOST_URL, ADMIN_API_KEY)


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Ciao, questo bot controlla quando {INSTAGRAM_PAGE} pubblica nuovi post su Instagram e li inoltra su Telegram e Ghost!')


async def _is_admin_of_channel(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Return True if the user is admin/creator of CHANNEL_ID."""
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return getattr(member, "status", "") in ("administrator", "creator")
    except Exception as e:
        logger.warning(f"Impossibile verificare permessi admin: {e}")
        return False


async def saved_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List saved Instagram posts in the database (only channel admins)."""
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id or not await _is_admin_of_channel(context, user_id):
        if update.message:
            await update.message.reply_text("Solo gli admin del canale possono usare questo comando.")
        return

    posts = db.get_all_posts()
    if not posts:
        await update.message.reply_text("Nessun post salvato nel database.")
        return

    message = "Post salvati nel database:\n"
    for shortcode, description in posts:
        message += f"- {shortcode}: {description[:50]}...\n" if description else f"- {shortcode}: (no description)\n"

    await update.message.reply_text(message)


async def check_new_posts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for new Instagram posts and send them to Telegram channel and Ghost."""
    try:
        loop = asyncio.get_running_loop()
        new_posts = await loop.run_in_executor(None, instagram.download_new_posts)

        new_posts.reverse()  # Send older posts first
        for post in new_posts:
            # Prepare caption with description and link
            link = f"\nhttps://instagram.com/p/{post['shortcode']}/"
            caption = ""
            if post['description']:
                description = post['description']
                if len(description) + len(link) > 1024:  # Telegram caption limit
                    caption = f"{description[:1020 - len(link)]}...{link}"
                else:
                    caption = f"{description}{link}"
            else:
                caption = link

            # Media folder under media_downloads/<shortcode>
            post_folder = Path("media_downloads") / post['shortcode']
            if not post_folder.exists():
                logger.warning(f"Post folder not found: {post_folder}")
                continue

            jpg_files = sorted(post_folder.glob('*.jpg'))
            mp4_files = sorted(post_folder.glob('*.mp4'))

            media_group = []
            file_handles = []

            try:
                # Photos
                for idx, jpg_file in enumerate(jpg_files):
                    f = open(jpg_file, 'rb')
                    file_handles.append(f)
                    if idx == 0:
                        media_group.append(InputMediaPhoto(f, caption=caption))
                    else:
                        media_group.append(InputMediaPhoto(f))

                # Videos
                for idx, mp4_file in enumerate(mp4_files):
                    file_size = mp4_file.stat().st_size / (1024 * 1024)
                    logger.info(f"Adding video {mp4_file} ({file_size:.2f} MB) to media group")
                    f = open(mp4_file, 'rb')
                    file_handles.append(f)
                    if idx == 0 and len(jpg_files) == 0:
                        media_group.append(InputMediaVideo(f, caption=caption))
                    else:
                        media_group.append(InputMediaVideo(f))

                if media_group:
                    await context.bot.send_media_group(
                        chat_id=CHANNEL_ID,
                        media=media_group,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=60,
                    )
                    db.insert_post(post['shortcode'], post['description'])
                    logger.info(f"Sent media group for post {post['shortcode']} to Telegram channel")

                # Create Ghost post
                image_paths = [str(p) for p in jpg_files]
                video_paths = [str(p) for p in mp4_files]
                title = (
                    f"{post['description'][:30]}..." if post.get('description')
                    else f"instagram post {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )

                ghost_post = ghost.create_media_post(
                    title=title,
                    image_paths=image_paths,
                    video_paths=video_paths,
                    description=post.get('description'),
                    status='published',
                    tags=['instagram', 'social-media'],
                )

                if ghost_post:
                    logger.info(f"✓ Created Ghost post: {ghost_post.get('title')} ({ghost_post.get('url')})")
                else:
                    logger.error(f"✗ Failed to create Ghost post for {post['shortcode']}")

            finally:
                for f in file_handles:
                    f.close()

            # Cleanup local media
            for file in post_folder.iterdir():
                file.unlink()
            post_folder.rmdir()
            logger.info(f"Deleted folder {post_folder} after sending media")

    except Exception as e:
        logger.error(f"Error checking new posts: {e}")


async def post_init(app) -> None:
    """Check for new posts when the application starts."""
    logger.info("Checking for new posts at startup")
    await check_new_posts(app)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("savedposts", saved_posts))
    #app.post_init = post_init

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_new_posts,
        'interval',
        hours=1,
        args=(app,),
        id='check_instagram_posts',
        name='Check Instagram Posts Every 1 Hour',
    )
    scheduler.start()

    logger.info("Scheduler started. Checking for new posts every 1 hour.")
    app.run_polling()


if __name__ == '__main__':
    main()