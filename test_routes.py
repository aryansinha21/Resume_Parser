#!/usr/bin/env python
import sys
sys.path.insert(0, '.')
from app import app

with app.app_context():
    client = app.test_client()
    response = client.get('/register')
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.content_type}")
    print(f"Data (first 500 chars):\n{response.data.decode('utf-8')[:500]}")
