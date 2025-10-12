#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config import settings

print("=== OAUTH URL DEBUGGING ===")
print(f"GITHUB_CLIENT_ID: {settings.GITHUB_CLIENT_ID}")
print(f"BACKEND_ORIGIN: {settings.BACKEND_ORIGIN}")
print(f"GITHUB_OAUTH_REDIRECT_URI: {settings.GITHUB_OAUTH_REDIRECT_URI}")

# Construct the OAuth URL like the auth router does
scopes = ["repo", "admin:repo_hook", "read:org"]
scope_param = "+".join(scopes)
oauth_url = (
    f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}"
    f"&redirect_uri={settings.GITHUB_OAUTH_REDIRECT_URI}&scope={scope_param}"
)

print(f"\nFull OAuth URL:")
print(oauth_url)

print(f"\nRedirect URI (isolated):")
print(f"'{settings.GITHUB_OAUTH_REDIRECT_URI}'")

print(f"\nURL Length: {len(settings.GITHUB_OAUTH_REDIRECT_URI)}")
print(f"Contains /prod: {'/prod' in settings.GITHUB_OAUTH_REDIRECT_URI}")
print(f"Starts with https://: {settings.GITHUB_OAUTH_REDIRECT_URI.startswith('https://')}")