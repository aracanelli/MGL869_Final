#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng



# F-Droid
FDROID_PROJECT_PATH = 'FDROID_REPOS_PATH'

REPO_URL_BLACK_LIST = ['https://github.com/benetech/Martus-Project',
                       'https://github.com/thialfihar/apg',
                       'https://github.com/free-software-for-android/Standalone-Calendar',
                       'https://github.com/adventuregamestudio/ags',
                       'https://github.com/scummvm/scummvm']

TARGET_APPS_URL = ['https://github.com/osmandapp/Osmand', 'https://github.com/wordpress-mobile/WordPress-Android',
                   'https://github.com/cgeo/cgeo', 'https://github.com/nextcloud/android']

LEVENSHTEIN_RATIO_THRESHOLD = 0.5

VALID_PROJECT_SLOC_THRESHOLD = 0

LOG_ONLY_COMMIT_LOC_DELTA_THRESHOLD = 4

GITHUB_API_TOKEN = 'GITHUB_TOKEN'
PROJECT_JAVA_CODE_PERCENTAGE_THRESHOLD = 0

# Database
DB_NAME = 'fdroid'
DB_USER = 'postgres'
DB_PASSWORD = ''
DB_HOST = '127.0.0.1'
DB_PORT = 5432


# Email
EMAIL_SENDER = 'XXX@XX.COM'
EMAIL_CC = 'YYY@XX.COM'


def get_repo_local_path_with_app_id(app_id):
    return FDROID_PROJECT_PATH + '/' + app_id

