#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

echo "--- Installing System Dependencies ---"
apt-get update && apt-get install -y wget gnupg

wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.conf

apt-get update && apt-get install -y \
    google-chrome-stable \
    libnss3 \
    libgbm1 \
    libasound2 \
    fonts-liberation

pip install --root-user-action=ignore -r requirements.txt
