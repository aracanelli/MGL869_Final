#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng

import sys
sys.path.append('../')
import csv
from pathlib import Path
import numpy as np
from logdetector.models import Repo, Log, LogChangeType
from logdetector import database
from logdetector import detector
from logdetector import config
from logdetector import metrics
from logdetector.utils import githelper
from logdetector.utils.latexwriter import LaTexWriter

def get_verbosity_level_number():
    all_repos = database.get_all_repos().order_by(Repo.app_id)
    total_verbose = 0
    total_debug = 0
    total_info = 0
    total_warn = 0
    total_error = 0
    total_other = 0

    title = 'Log Verbosity Level Distribution'
    label = 'tab:log_level_distribution'
    header = ['Software', 'VERBOSE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'OTHER']
    data = []

    for repo in all_repos:
        verbose, debug, info, warn, error, other = detector.get_verbosity_level_distribution_of_repo(repo)
        if repo.url in config.TARGET_APPS_URL:
            print('{}  verbose: {}, debug: {}, info: {}, warn: {}, error: {}'.format(repo.app_id, verbose, debug, info, warn, error))
            data.append([repo.name, verbose, debug, info, warn, error, other])
        total_verbose += verbose
        total_debug += debug
        total_info += info
        total_warn += warn
        total_error += error
        total_other += other
    print('total verbose: {}, debug: {}, info: {}, warn: {}, error: {}, other: {}'.format(total_verbose, total_debug, total_info, total_warn, total_error, total_other))
    data.insert(0, ['All F-Droid Projects', total_verbose, total_debug, total_info, total_warn, total_error, total_other])
    writer = LaTexWriter(title, label, header, data)
    writer.print()


def get_churn_rate():
    all_repos = database.get_all_repos().order_by(Repo.app_id)
    repos_with_log = []
    for repo in all_repos:
        if repo.logging_loc > 0 and repo.sloc > 713:
            repos_with_log.append(repo)

    churn_rate_list = []
    logging_churn_rate_list = []
    for repo in repos_with_log:
        churn_rate = metrics.get_average_churn_rate_of_repo(repo)
        logging_churn_rate = metrics.get_average_logging_churn_rate_or_repo(repo)
        if churn_rate is not None:
            churn_rate_list.append(churn_rate)
            logging_churn_rate_list.append(logging_churn_rate)

    print('churn rate:')
    get_arithmetic_result_of_list(churn_rate_list)

    print('logging churn rate:')
    get_arithmetic_result_of_list(logging_churn_rate_list)


def get_arithmetic_result_of_list(data: list):
    array = np.array(data)
    quartile = np.percentile(array, np.arange(0, 101, 25))
    mean = np.mean(array)
    print('mean: {}, quartile: {}'.format(mean, quartile))


def get_loc_distribution():
    all_repos = database.get_all_repos().order_by(Repo.app_id)

    repos_with_log = []
    for repo in all_repos:
        if repo.logging_loc > 0 and repo.sloc > 713:
            repos_with_log.append(repo)

    sloc_list = [x.sloc for x in all_repos]
    lolc_list = [x.logging_loc for x in repos_with_log]
    log_density_list = [x.sloc / x.logging_loc for x in repos_with_log]
    commits_list = [x.commits_num for x in all_repos]
    files_list = [x.files_num for x in all_repos]
    print('sloc:')
    get_arithmetic_result_of_list(sloc_list)

    print('lolc:')
    get_arithmetic_result_of_list(lolc_list)

    print('log density:')
    get_arithmetic_result_of_list(log_density_list)

    print('commits:')
    get_arithmetic_result_of_list(commits_list)

    print('files:')
    get_arithmetic_result_of_list(files_list)


def get_log_update_type():
    all_updated_logs = database.Log.select().where(Log.change_type == LogChangeType.UPDATED)
    for log in all_updated_logs:
        update_type = metrics.get_log_update_detail(log)
        log.update_type = update_type
        log.save()


def get_author_distribution():
    all_repos = database.get_all_repos().order_by(Repo.app_id)
    authors_list = [x.authors_num for x in all_repos]
    print('authors:')
    get_arithmetic_result_of_list(authors_list)


def main():
    get_verbosity_level_number()
    get_churn_rate()
    get_loc_distribution()
    get_author_distribution()
    get_log_update_type()


if __name__ == '__main__':
    main()
