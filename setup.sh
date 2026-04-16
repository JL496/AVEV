#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

# 1. Install Chromium, the Driver, and the missing libraries (Fixes Status 127)
apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libnss3 \
    libgbm1 \
    libasound2

# 2. Install Python packages and ignore the root warning
pip install --root-user-action=ignore -r requirements.txt
