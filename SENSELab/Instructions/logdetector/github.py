#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng


import json
import urllib.request
from logdetector import config


GITHUB_API_URL = 'https://api.github.com'


def _get_language_url(owner, repo_name):
    return '{}/repos/{}/{}/languages'.format(GITHUB_API_URL, owner, repo_name)


def get_json_response_from_url(url):
    request = urllib.request.Request(url)
    request.add_header('Authorization', 'token {}'.format(config.GITHUB_API_TOKEN))

    try:
        response = urllib.request.urlopen(request)
        raw_data = response.read().decode('utf-8')
        result = json.loads(raw_data)
    except Exception as e:
        result = {}

    return result


def is_java_project(repo_url: str):
    if 'github.com' not in repo_url:
        return False

    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]
    if repo_url.endswith('/'):
        repo_url = repo_url[:-1]
    url_components = repo_url.split('/')
    owner = url_components[-2]
    repo_name = url_components[-1]
    language_url = _get_language_url(owner, repo_name)
    response = get_json_response_from_url(language_url)
    total_bytes = sum(response.values())
    if total_bytes > 0:
        return (response.get('Java', 0) / total_bytes) > config.PROJECT_JAVA_CODE_PERCENTAGE_THRESHOLD
    else:
        return False
