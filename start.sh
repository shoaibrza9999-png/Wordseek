#!/bin/bash
# Re-create database schema on start
python3 database.py
# Start gunicorn
gunicorn -b 0.0.0.0:$PORT 'bot:app'
