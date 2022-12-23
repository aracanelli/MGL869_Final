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

TARGET_APPS_URL = ['https://github.com/yourealwaysbe/forkyz',
                   'https://github.com/agateau/pixelwheels',
                   'https://github.com/moonlight-stream/moonlight-android',
                   'https://github.com/00-Evan/shattered-pixel-dungeon',
                   'https://github.com/RailwayStations/RSAndroidApp',
                   'https://github.com/Anuken/Mindustry',
                   'https://github.com/vcmi/vcmi-android',
                   'https://github.com/jcarolus/android-chess',
                   'https://github.com/dolphin-emu/dolphin',
                   'https://github.com/IITC-CE/ingress-intel-total-conversion',
                   'https://github.com/mupen64plus-ae/mupen64plus-ae',
                   'https://github.com/hrydgard/ppsspp',
                   'https://github.com/scoutant/blokish',
                   'https://github.com/SecUSo/privacy-friendly-werewolf',
                   'https://github.com/nikita36078/J2ME-Loader']

LEVENSHTEIN_RATIO_THRESHOLD = 0.5

VALID_PROJECT_SLOC_THRESHOLD = 0

LOG_ONLY_COMMIT_LOC_DELTA_THRESHOLD = 4

GITHUB_API_TOKEN = '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'
PROJECT_JAVA_CODE_PERCENTAGE_THRESHOLD = 0

# Database
DB_NAME = 'postgres'
DB_USER = 'rac'
DB_PASSWORD = '030366'
DB_HOST = '127.0.0.1'
DB_PORT = 5432


# Email
EMAIL_SENDER = 'anthony.racanelli.1@ens.etsmtl.ca'
EMAIL_CC = 'anthony.racanelli.1@ens.etsmtl.ca'


def get_repo_local_path_with_app_id(app_id):
    return FDROID_PROJECT_PATH + '/' + app_id

