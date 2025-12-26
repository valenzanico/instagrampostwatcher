# Instagram post watcher and publisher bot
This project check every hour for new posts on a specified Instagram page and pubblishes them on a telegram channel and a Ghost blog.

pm2 start ./src/main.py --name igpostwatcher --interpreter ./venv/bin/python --cwd .