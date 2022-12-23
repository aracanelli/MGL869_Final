#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng

# DO IT AFTER YOU GET THE fdroid_github.csv
import sys
sys.path.append('../')
import csv
from pathlib import Path
from logdetector import database
from logdetector.utils import shellhelper
from logdetector import config
from logdetector import github
from logdetector.models import Repo
from logdetector.utils import filehelper


def initialize_repo_database():
    database.create_tables()


def get_local_project_ids(local_projects_dir):
    path = Path(local_projects_dir)
    projects = [str(x.relative_to(local_projects_dir)) for x in path.iterdir() if x.is_dir()]
    local_project_ids = [x for x in projects if '.' in x]
    return local_project_ids


def get_fdroid_repos(path: str):
    csv_repos = {}
    p = Path(path)
    with p.open(encoding='utf-8') as f:
        next(f)
        reader = csv.reader(f)
        for row in reader:
            csv_repos[row[1]] = row
    return csv_repos


def save_repos_to_db(csv_path: str):
    csv_repos = get_fdroid_repos(csv_path)
    git_clone_fdroid_repos(csv_repos)
    local_project_ids = get_local_project_ids(config.FDROID_PROJECT_PATH)

    for local_app_id in local_project_ids:
        csv_repo = csv_repos.get(local_app_id)
        if csv_repo is not None:
            app_url = csv_repo[0]
            app_id = csv_repo[1]
            app_name = csv_repo[2]

            repo = database.get_repo_with_url(app_url)
            if repo is None:
                Repo.create(url=app_url, app_id=app_id, name=app_name)
            else:
                repo.app_id = app_id
                repo.name = app_name
                repo.save()


def git_clone_fdroid_repos(csv_repos: dict):
    for app_id, app in csv_repos.items():
        app_url = app[0]
        repo_path = config.get_repo_local_path_with_app_id(app_id)

        if app_url not in config.REPO_URL_BLACK_LIST and\
                not filehelper.is_file_exists(repo_path) and\
                github.is_java_project(app_url):
            # git clone projects which are not in black list, not exist in local, and contain Java code
            shellhelper.run("git clone {} '{}'".format(app_url, repo_path))


if __name__ == '__main__':
    initialize_repo_database()
    fdroid_csv_path = '../data/fdroid_github.csv'
    save_repos_to_db(fdroid_csv_path)
