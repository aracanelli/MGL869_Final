#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng

import sys
sys.path.append('../')
from datetime import datetime
from logdetector import database
from logdetector import detector


def main():
    all_repos = database.get_all_repos().order_by(database.Repo.app_id)
    for repo in all_repos:
        detector.detect_project(repo, True, None)


if __name__ == '__main__':
    main()
