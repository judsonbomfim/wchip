# gunicorn_config.py

bind = "0.0.0.0:8000"
module = "aurigaone.wsgi:application"

workers = 4  # Adjust based on your server's resources
worker_connections = 1000
threads = 4

certfile = "/etc/letsencrypt/live/painel.worldchip.com.br/fullchain.pem"
keyfile = "/etc/letsencrypt/live/painel.worldchip.com.br/privkey.pem"