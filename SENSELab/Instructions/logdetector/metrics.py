#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng

import sys
sys.path.append('../')
import logging
from logdetector.models import Repo, Commit, Log, LogChangeType, LogUpdateType, LogVerbosityType
from logdetector import config
from logdetector import database
from logdetector import codetransform


logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)


def get_churn_rate_of_commit(commit: Commit):
    if commit.code_churn is not None and commit.sloc > 0:
        return commit.code_churn / commit.sloc
    else:
        return 0


def get_logging_churn_rate_of_commit(commit: Commit):
    if commit.logging_code_churn is not None and commit.logging_loc > 0:
        return commit.logging_code_churn / commit.logging_loc
    else:
        return 0


def get_average_churn_rate_of_repo(repo: Repo):
    if repo.is_repo_valid():
        commits = repo.get_non_merge_commits()
        return sum(get_churn_rate_of_commit(commit) for commit in commits) / len(commits)
    else:
        return None


def get_average_logging_churn_rate_or_repo(repo: Repo):
    if repo.is_repo_valid():
        commits = repo.get_non_merge_commits()
        return sum(get_logging_churn_rate_of_commit(commit) for commit in commits) / len(commits)
    else:
        return None


def is_commit_log_related(commit: Commit):
    return commit.logging_code_churn > 0


def is_commit_only_log_related(commit: Commit):
    return abs(commit.code_churn - commit.logging_code_churn) < config.LOG_ONLY_COMMIT_LOC_DELTA_THRESHOLD


def get_deleted_inside_method_log_ages_of_repo(repo: Repo):
    all_logs = database.get_logs_of_repo(repo)
    deleted_inside_method_logs = list(filter(lambda x: x.change_type == LogChangeType.DELETED_INSIDE_METHOD, all_logs))
    updated_logs = list(filter(lambda x: x.is_type_updated(), all_logs))
    added_logs = list(filter(lambda x: x.is_type_added(), all_logs))
    not_found_count = 0
    total_age_seconds = 0
    age_list = []

    for deleted_log in deleted_inside_method_logs:
        tmp_candidate = deleted_log
        logger.debug('deleted log: {}, {}, {}, {} '.format(deleted_log.commit.commit_id, deleted_log.file_path, deleted_log.embed_method, deleted_log.content))
        root_updated_candidate = None
        # Find if the log is updated before deleted, if so, find the earliest one.
        while tmp_candidate is not None:
            root_updated_candidate = tmp_candidate
            tmp_candidate = find_candidate_of_log(root_updated_candidate, updated_logs)

        compare_candidate = root_updated_candidate

        # Find the one added in the first place
        added_from = find_candidate_of_log(compare_candidate, added_logs)
        if added_from is None:
            logger.warning('not added log found for : {}, {}, {}, {} '.format(compare_candidate.commit.commit_id, compare_candidate.file_path, compare_candidate.embed_method, compare_candidate.content))
            not_found_count += 1
        else:
            delete_date = deleted_log.commit.committed_date
            added_date = added_from.commit.committed_date
            age = delete_date - added_date
            age_seconds = age.total_seconds()
            total_age_seconds += age_seconds
            age_list.append(age_seconds)

    logger.info('total deleted inside method logs count: {}, not found: {}'.format(len(deleted_inside_method_logs), not_found_count))
    return age_list


def find_candidate_of_log(target_log: Log, source_logs: [Log]) -> Log:
    candidates = []
    compare_candidate = None
    for source_log in source_logs:
        if target_log.is_type_deleted():
            if source_log.content == target_log.content:
                if source_log.commit.committed_date < target_log.commit.committed_date:
                    candidates.append(source_log)
        elif target_log.is_type_updated():
            if source_log.content == target_log.content_update_from:
                if source_log.commit.committed_date < target_log.commit.committed_date:
                    candidates.append(source_log)

    if len(candidates) > 0:
        for candidate in candidates:
            candidate_file_name = candidate.file_path.split('/')[-1]
            candidate_method = candidate.embed_method.split('(')[0]
            target_file_name = target_log.file_path.split('/')[-1]
            target_method = target_log.file_path.split('(')[0]
            if candidate_file_name == target_file_name and candidate_method == target_method:
                compare_candidate = candidate
                break

        if compare_candidate is None:
            # Poor workaround for file renaming situation, maybe should use git follow.
            for candidate in candidates:
                candidate_method = candidate.embed_method.split('(')[0]
                target_method = target_log.embed_method.split('(')[0]
                if candidate_method == target_method:
                    compare_candidate = candidate
                    break

        if compare_candidate is None:
            # Poor workaround for method renaming situation, maybe should use git follow.
            for candidate in candidates:
                candidate_file_name = candidate.file_path.split('/')[-1]
                target_file_name = target_log.file_path.split('/')[-1]
                if candidate_file_name == target_file_name:
                    compare_candidate = candidate
                    break

    return compare_candidate


def get_log_update_detail(log: Log):
    if log.change_type != LogChangeType.UPDATED:
        return None

    update_type = ''
    old_content = log.content_update_from.replace('\\n', '').replace('\\t', '').replace('\\r', '')
    new_content = log.content.replace('\\n', '').replace('\\t', '').replace('\\r', '')
    if ''.join(old_content.split()) == ''.join(new_content.split()):
        update_type = LogUpdateType.UPDATED_FORMAT
    else:
        # Check logging method and verbosity
        old_caller_object, old_verbosity_type = get_log_content_component(old_content)
        new_caller_object, new_verbosity_type = get_log_content_component(new_content)
        if old_caller_object != new_caller_object:
            update_type = LogUpdateType.UPDATED_LOGGING_METHOD
        if old_verbosity_type is not None \
                and new_verbosity_type is not None\
                and old_verbosity_type != new_verbosity_type:
                update_type = update_type + '+' + LogUpdateType.UPDATED_VERBOSITY + '_' + old_verbosity_type + '_TO_' + new_verbosity_type

        # Check argument
        new_log_xml = codetransform.transform_log_str_to_xml_obj(new_content)
        new_log_texts = codetransform.get_all_text_str_in_call(new_log_xml)
        new_log_vars = codetransform.get_all_var_str_in_call(new_log_xml)
        new_log_sims = codetransform.get_all_sim_str_in_call(new_log_xml)

        old_log_xml = codetransform.transform_log_str_to_xml_obj(old_content)
        old_log_texts = codetransform.get_all_text_str_in_call(old_log_xml)
        old_log_vars = codetransform.get_all_var_str_in_call(old_log_xml)
        old_log_sims = codetransform.get_all_sim_str_in_call(old_log_xml)

        if new_log_xml is not None and old_log_xml is not None:
            # Check text
            if len(new_log_texts) > len(old_log_texts):
                update_type = update_type + '+' + LogUpdateType.ADDED_TEXT
            elif len(new_log_texts) < len(old_log_texts):
                update_type = update_type + '+' + LogUpdateType.DELETED_TEXT
            else:
                new_words = sum([x.split() for x in new_log_texts], [])
                old_words = sum([x.split() for x in old_log_texts], [])
                if len(new_words) > len(old_words):
                    update_type = update_type + '+' + LogUpdateType.ADDED_TEXT
                elif len(new_words) < len(old_words):
                    update_type = update_type + '+' + LogUpdateType.DELETED_TEXT
                else:
                    new_text_set = set(new_log_texts) - set(old_log_texts)
                    if len(new_text_set) > 0:
                        update_type = update_type + '+' + LogUpdateType.REPLACED_TEXT

            # Check var
            if len(new_log_vars) > len(old_log_vars):
                update_type = update_type + '+' + LogUpdateType.ADDED_VAR
            if len(new_log_vars) < len(old_log_vars):
                update_type = update_type + '+' + LogUpdateType.DELETED_VAR
            else:
                new_var_set = set(new_log_vars) - set(old_log_vars)
                if len(new_var_set) > 0:
                    update_type = update_type + '+' + LogUpdateType.REPLACED_VAR

            # Check SIM
            if len(new_log_sims) > len(old_log_sims):
                update_type = update_type + '+' + LogUpdateType.ADDED_SIM
            if len(new_log_sims) < len(old_log_sims):
                update_type = update_type + '+' + LogUpdateType.DELETED_SIM
            else:
                new_log_set = set(new_log_sims) - set(old_log_sims)
                if len(new_log_set) > 0:
                    update_type = update_type + '+' + LogUpdateType.REPLACED_SIM

    if update_type.startswith('+'):
        update_type = update_type[1:]

    if update_type == '':
        return None
    else:
        return update_type


def get_log_content_component(content: str):
    caller_method = content.split('(')[0]
    caller_method = ''.join(caller_method.split())
    if '.' in caller_method:
        verbosity = caller_method.split('.')[-1]
        caller_object = caller_method.rsplit('.', 1)[0]
    else:
        caller_object = caller_method
        verbosity = caller_method
    verbosity_type = get_verbosity_type(caller_object, verbosity)
    arguments_str = content[len(caller_method) + 1: -1]
    arguments = arguments_str.split(',')
    return caller_object, verbosity_type


def get_verbosity_type(caller: str, verbosity: str):
    if caller == 'System.err':
        return LogVerbosityType.ERROR
    if caller == 'System.out':
        return LogVerbosityType.INFO

    verbosity_type = None
    if verbosity is not None:
        lowercase_verbosity = verbosity.lower()
        if lowercase_verbosity in ['v', 'verbose', 'logv', 'logverbose', 'verboselog', 'log_v', 'trace']:
            verbosity_type = LogVerbosityType.VERBOSE
        elif lowercase_verbosity in ['d', 'debug', 'fine', 'logd', 'logdebug', 'debuglog', 'log_d']:
            verbosity_type = LogVerbosityType.DEBUG
        elif lowercase_verbosity in ['i', 'info',  'log', 'logi', 'logln', 'loginfo', 'infolog', 'log_i',
                                     'print', 'printf', 'println', 'printlog', 'logmessage', 'logcommon']:
            verbosity_type = LogVerbosityType.INFO
        elif lowercase_verbosity in ['w', 'warn', 'warning', 'logw', 'logwarning', 'logwarn', 'warnlog',
                                     'warninglog', 'log_w']:
            verbosity_type = LogVerbosityType.WARN
        elif lowercase_verbosity in ['e', 'error', 'severe', 'fatal', 'wtf', 'loge', 'logerror', 'logsevere', 'logfatal',
                                     'logwtf', 'logexception', 'errlog', 'errorlog', 'severelog', 'fatallog', 'log_e']:
            verbosity_type = LogVerbosityType.ERROR

    return verbosity_type


