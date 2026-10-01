# Nginx Configuration

To set up HTTPS and a reverse proxy on your Oracle Cloud server using Nginx, follow these steps:

1. Install Nginx:
   `sudo apt install nginx -y`
   
2. Create a new site config in `/etc/nginx/sites-available/pb-hero`:
```nginx
server {
    server_name panel.example.com; # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_addrs;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSockets support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

3. Enable the site:
   `sudo ln -s /etc/nginx/sites-available/pb-hero /etc/nginx/sites-enabled/`

4. Install Certbot and get SSL:
   `sudo apt install certbot python3-certbot-nginx -y`
   `sudo certbot --nginx -d panel.example.com`
