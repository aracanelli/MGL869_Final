#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng


import logging
from datetime import datetime
import Levenshtein
from lxml import etree
from logdetector import codetransform
from logdetector.utils import filehelper
from logdetector.utils import githelper
from logdetector.utils import shellhelper
from logdetector.utils import urlhelper
from logdetector import config
from logdetector import getloc
from logdetector import metrics
from logdetector.models import Repo, Commit, Log, LogChangeType, LogUpdateType, LogArgumentType, LogVerbosityType


logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)


def diff_inspector(git_repo, commit_diff, head_commit_db: Commit):
    head_commit_sha = head_commit_db.commit_id
    head_commit_git = git_repo.commit(head_commit_sha)
    head_commit_db.committer_name = head_commit_git.committer.name
    head_commit_db.committer_email = head_commit_git.committer.email
    head_commit_db.committed_date = head_commit_git.committed_datetime
    head_commit_db.author_name = head_commit_git.author.name
    head_commit_db.author_email = head_commit_git.author.email
    head_commit_db.authored_date = head_commit_git.authored_datetime
    head_commit_db.message = head_commit_git.message

    repo_added_sloc = 0
    repo_deleted_sloc = 0
    repo_updated_sloc = 0

    repo_added_logging_loc = 0
    repo_deleted_logging_loc = 0
    repo_updated_logging_loc = 0

    for file_diff in commit_diff:

        if file_diff.change_type == 'A':
            file_sloc, file_logging_loc = handle_added_file(file_diff, head_commit_db)
            repo_added_sloc += file_sloc
            repo_added_logging_loc += file_logging_loc
        elif file_diff.change_type == 'D':
            file_sloc, file_logging_loc = handle_deleted_file(file_diff, head_commit_db)
            repo_deleted_sloc += file_sloc
            repo_deleted_logging_loc += file_logging_loc
        elif file_diff.change_type == 'M' or \
                (file_diff.change_type.startswith('R') and file_diff.a_blob != file_diff.b_blob):
            file_added_sloc, file_deleted_sloc, file_updated_sloc, file_added_logging_loc, file_deleted_logging_loc, file_updated_logging_loc = \
                handle_updated_file(file_diff, head_commit_db)

            repo_added_sloc += file_added_sloc
            repo_deleted_sloc += file_deleted_sloc
            repo_updated_sloc += file_updated_sloc
            repo_added_logging_loc += file_added_logging_loc
            repo_deleted_logging_loc += file_deleted_logging_loc
            repo_updated_logging_loc += file_updated_logging_loc

    code_churn = repo_added_sloc + repo_deleted_sloc + (repo_updated_sloc * 2)
    sloc_delta = repo_added_sloc - repo_deleted_sloc
    logging_code_churn = repo_added_logging_loc + repo_deleted_logging_loc + (repo_updated_logging_loc * 2)
    logging_loc_delta = repo_added_logging_loc - repo_deleted_logging_loc

    head_commit_db.code_churn = code_churn
    head_commit_db.logging_code_churn = logging_code_churn
    head_commit_db.save()

    return sloc_delta, logging_loc_delta


def handle_added_file(file_diff, head_commit_db: Commit):
    return handle_added_or_deleted_file(file_diff.b_path, file_diff.b_blob,
                                        LogChangeType.ADDED_WITH_FILE, head_commit_db)


def handle_deleted_file(file_diff, head_commit_db: Commit):
    return handle_added_or_deleted_file(file_diff.a_path, file_diff.a_blob,
                                        LogChangeType.DELETED_WITH_FILE, head_commit_db)


def handle_updated_file(file_diff, head_commit_db: Commit):
    file_added_sloc = 0
    file_deleted_sloc = 0
    file_updated_sloc = 0
    file_added_logging_loc = 0
    file_deleted_logging_loc = 0
    file_updated_logging_loc = 0

    if filehelper.is_java_file(file_diff.a_path) and filehelper.is_java_file(file_diff.b_path):
        java_a_file = codetransform.generate_java_file_of_blob(file_diff.a_blob)
        java_b_file = codetransform.generate_java_file_of_blob(file_diff.b_blob)
        loc_diff = getloc.get_java_loc_diff(java_a_file, java_b_file)
        filehelper.delete_if_exists(java_a_file)
        filehelper.delete_if_exists(java_b_file)

        file_added_sloc = loc_diff['added'].code_num
        file_deleted_sloc = loc_diff['removed'].code_num
        file_updated_sloc = loc_diff['modified'].code_num

        methods_parent = codetransform.get_methods_of_java_blob(file_diff.a_blob)
        methods_head = codetransform.get_methods_of_java_blob(file_diff.b_blob)
        file_added_logging_loc, file_deleted_logging_loc, file_updated_logging_loc = \
            compare_all_methods(methods_parent, methods_head, file_diff, head_commit_db)

        logger.debug('updated file: {}, added_sloc: {}, deleted_sloc: {}, updated_sloc: {}, added_lolc: {}, deleted_lolc: {}, updated_lolc: {}'.format(
                file_diff.b_path, file_added_sloc, file_deleted_sloc, file_updated_sloc, file_added_logging_loc, file_deleted_logging_loc, file_updated_logging_loc
            ))

    return file_added_sloc, file_deleted_sloc, file_updated_sloc, file_added_logging_loc, file_deleted_logging_loc, file_updated_logging_loc


def handle_added_or_deleted_file(file_path, file_blob, change_type, head_commit_db: Commit):
    file_sloc = 0
    file_logging_loc = 0

    if filehelper.is_java_file(file_path):
        java_file = codetransform.generate_java_file_of_blob(file_blob)
        file_sloc = getloc.get_java_sloc(java_file)
        file_logging_loc = getloc.get_logging_loc_of_file(java_file)
        filehelper.delete_if_exists(java_file)

        if not head_commit_db.is_merge_commit:
            methods = codetransform.get_methods_of_java_blob(file_blob)
            for method in methods:
                method_str = b'<root>' + etree.tostring(method) + b'</root>'
                save_logs_of_method_xml_str_if_needed(change_type, file_path, head_commit_db, method_str)

        if change_type == LogChangeType.ADDED_WITH_FILE:
            logger.debug('added file: {},  sloc: {}, logging_loc: {}'.format(file_path, file_sloc, file_logging_loc))
        elif change_type == LogChangeType.DELETED_WITH_FILE:
            logger.debug('deleted file: {},  sloc: {}, logging_loc: {}'.format(file_path, file_sloc, file_logging_loc))

    return file_sloc, file_logging_loc


def save_logs_of_method_xml_str_if_needed(change_type, file_path, head_commit_db, method_str):
    method = etree.fromstring(method_str)
    method_name = codetransform.get_method_full_signature(method)
    logging_calls = codetransform.get_logging_calls_xml_of_method(method)
    if not head_commit_db.is_merge_commit:
        for call_xml in logging_calls:
            save_logs_of_logging_call_xml(call_xml, change_type, file_path, head_commit_db, method_name)
    return len(logging_calls)


def save_logs_of_logging_call_xml(call_xml, change_type, file_path, head_commit_db, method_name):
    call_text = codetransform.transform_xml_str_to_code(etree.tostring(call_xml).decode('utf-8'))
    call_name = codetransform.get_method_call_name(call_xml)
    if '.' in call_name:
        verbosity = call_name.split('.')[-1]
    else:
        verbosity = call_name
    argument_type = get_logging_argument_type(call_xml)
    _, verbosity_type = metrics.get_log_content_component(call_text)
    Log.create(commit=head_commit_db, file_path=file_path, embed_method=method_name, change_type=change_type,
               content=call_text, verbosity=verbosity, verbosity_type=verbosity_type, argument_type=argument_type)


def compare_all_methods(methods_parent, methods_head, file_diff, head_commit_db: Commit):
    file_added_logging_loc = 0
    file_deleted_logging_loc = 0
    file_updated_logging_loc = 0

    method_parent_strings = [etree.tostring(method) for method in methods_parent]
    method_head_strings = [etree.tostring(method) for method in methods_head]

    # Get methods in parent and not in head
    methods_only_in_parent = get_complement_of_a_in_b(method_head_strings, method_parent_strings)
    methods_only_in_parent = list(map((lambda method_str: b'<root>' + method_str + b'</root>'), methods_only_in_parent))

    # Get methods in head and not in parent
    methods_only_in_head = get_complement_of_a_in_b(method_parent_strings, method_head_strings)
    methods_only_in_head = list(map((lambda method_str: b'<root>' + method_str + b'</root>'), methods_only_in_head))

    methods_str_already_checked_in_parent = []
    methods_str_already_checked_in_head = []

    # 1. Compare methods with same signature.
    for method_parent_str in methods_only_in_parent:
        # method_parent_str = b'<root>' + method_parent_str + b'</root>'
        method_parent_xml = etree.fromstring(method_parent_str)
        for method_head_str in methods_only_in_head:
            # method_head_str = b'<root>' + method_head_str + b'</root>'
            if method_head_str in methods_str_already_checked_in_head:
                continue
            method_head_xml = etree.fromstring(method_head_str)
            is_same_name, is_same_parameters = codetransform.compare_method_signature(method_parent_xml, method_head_xml)
            if is_same_name and is_same_parameters:
                # Methods with same signature, it is modified
                logging_method_calls_in_parent = codetransform.get_logging_calls_xml_of_method(method_parent_xml)
                logging_method_calls_in_head = codetransform.get_logging_calls_xml_of_method(method_head_xml)
                method_name = codetransform.get_method_full_signature(method_head_xml)
                method_added_logging_loc, method_deleted_logging_loc, method_updated_logging_loc = \
                    compare_logging_method_calls(head_commit_db, file_diff, method_name,
                                                 logging_method_calls_in_parent, logging_method_calls_in_head)
                file_added_logging_loc += method_added_logging_loc
                file_deleted_logging_loc += method_deleted_logging_loc
                file_updated_logging_loc += method_updated_logging_loc
                methods_str_already_checked_in_parent.append(method_parent_str)
                methods_str_already_checked_in_head.append(method_head_str)
                break

    # 2. Compare rest methods with different signature
    for method_parent_str in methods_only_in_parent:
        # method_parent_str = b'<root>' + method_parent_str + b'</root>'
        if method_parent_str in methods_str_already_checked_in_parent:
            continue
        method_parent_xml = etree.fromstring(method_parent_str)
        for method_head_str in methods_only_in_head:
            # method_head_str = b'<root>' + method_head_str + b'</root>'
            if method_head_str in methods_str_already_checked_in_head:
                continue
            method_head_xml = etree.fromstring(method_head_str)
            is_same_name, is_same_parameters = codetransform.compare_method_signature(method_parent_xml, method_head_xml)
            block_content_str_in_parent = etree.tostring(codetransform.get_method_block_content(method_parent_xml))
            block_content_str_in_head = etree.tostring(codetransform.get_method_block_content(method_head_xml))
            if is_same_name and not is_same_parameters:
                #  if method name are same, that is parameter declaration change.
                if block_content_str_in_parent == block_content_str_in_head:
                    # text are same, no need to compare
                    pass
                else:
                    # if text not same, method is modified, deal with the same process above.
                    logging_method_calls_in_parent = codetransform.get_logging_calls_xml_of_method(method_parent_xml)
                    logging_method_calls_in_head = codetransform.get_logging_calls_xml_of_method(method_head_xml)
                    method_name = codetransform.get_method_full_signature(method_head_xml)
                    method_added_logging_loc, method_deleted_logging_loc, method_updated_logging_loc = \
                        compare_logging_method_calls(head_commit_db, file_diff, method_name,
                                                     logging_method_calls_in_parent, logging_method_calls_in_head)
                    file_added_logging_loc += method_added_logging_loc
                    file_deleted_logging_loc += method_deleted_logging_loc
                    file_updated_logging_loc += method_updated_logging_loc
                methods_str_already_checked_in_parent.append(method_parent_str)
                methods_str_already_checked_in_head.append(method_head_str)
            elif not is_same_name and not is_same_parameters:
                if block_content_str_in_parent == block_content_str_in_head:
                    # if text are same, no log changed. They are renamed method.
                    methods_str_already_checked_in_parent.append(method_parent_str)
                    methods_str_already_checked_in_head.append(method_head_str)

    # 3. For the rest methods, they are added or deleted
    for method_parent_str in methods_only_in_parent:
        # method_parent_str = b'<root>' + method_parent_str + b'</root>'
        if method_parent_str not in methods_str_already_checked_in_parent:
            # they are deleted, mark log calls in those methods as deleted.
            file_deleted_logging_loc += save_logs_of_method_xml_str_if_needed(LogChangeType.DELETED_WITH_METHOD,
                                                                              file_diff.a_path, head_commit_db, method_parent_str)
    for method_head_str in methods_only_in_head:
        # method_head_str = b'<root>' + method_head_str + b'</root>'
        if method_head_str not in methods_str_already_checked_in_head:
            # they are added, mark log calls in those methods as added.
            file_added_logging_loc += save_logs_of_method_xml_str_if_needed(LogChangeType.ADDED_WITH_METHOD,
                                                                            file_diff.b_path, head_commit_db, method_head_str)

    return file_added_logging_loc, file_deleted_logging_loc, file_updated_logging_loc


def compare_logging_method_calls(head_commit_db: Commit, file_diff, method_name, logging_method_calls_parent, logging_method_calls_head):
    method_mapping_list = []
    method_added_logging_loc = 0
    method_deleted_logging_loc = 0
    method_updated_logging_loc = 0

    # Add index to make each call unique.
    method_calls_str_parent = \
        [str(index) + '#' + etree.tostring(call).decode('utf-8') for index, call in enumerate(logging_method_calls_parent)]
    method_calls_str_head = \
        [str(index) + '#' + etree.tostring(call).decode('utf-8') for index, call in enumerate(logging_method_calls_head)]

    for call_str_in_parent in method_calls_str_parent:
        for call_str_in_head in method_calls_str_head:
            distance_ratio = Levenshtein.ratio(codetransform.transform_xml_str_to_code(call_str_in_parent),
                                               codetransform.transform_xml_str_to_code(call_str_in_head))
            if distance_ratio > config.LEVENSHTEIN_RATIO_THRESHOLD:
                is_parent_in_mapping = False
                # Check mapping list
                for mapping in method_mapping_list:
                    call_mapping_parent = mapping[0]
                    mapping_ratio = mapping[2]
                    if call_str_in_parent == call_mapping_parent:
                        is_parent_in_mapping = True
                        if distance_ratio > mapping_ratio:
                            mapping[1] = call_str_in_head
                            mapping[2] = Levenshtein.ratio(_get_code_text_from_compare(call_str_in_parent),
                                                           _get_code_text_from_compare(call_str_in_head))
                if not is_parent_in_mapping:
                    is_head_in_mapping = False
                    for mapping in method_mapping_list:
                        call_mapping_head = mapping[1]
                        mapping_ratio = mapping[2]
                        if call_str_in_head == call_mapping_head:
                            is_head_in_mapping = True
                            if distance_ratio > mapping_ratio:
                                mapping[0] = call_str_in_parent
                                mapping[2] = Levenshtein.ratio(_get_code_text_from_compare(call_str_in_parent),
                                                               _get_code_text_from_compare(call_str_in_head))
                    if not is_head_in_mapping:
                        method_mapping_list.append([call_str_in_parent, call_str_in_head, distance_ratio])

    method_calls_mapping_in_parent = [mapping[0] for mapping in method_mapping_list]
    method_calls_mapping_in_head = [mapping[1] for mapping in method_mapping_list]

    deleted_logging_calls_str = list(set(method_calls_str_parent) - set(method_calls_mapping_in_parent))
    added_logging_calls_str = list(set(method_calls_str_head) - set(method_calls_mapping_in_head))

    method_deleted_logging_loc += len(deleted_logging_calls_str)
    method_added_logging_loc += len(added_logging_calls_str)

    if not head_commit_db.is_merge_commit:
        for call_str in deleted_logging_calls_str:
            call_xml = etree.fromstring(_get_code_xml_str_from_compare(call_str))
            save_logs_of_logging_call_xml(call_xml, LogChangeType.DELETED_INSIDE_METHOD, file_diff.a_path, head_commit_db, method_name)

        for call_str in added_logging_calls_str:
            call_xml = etree.fromstring(_get_code_xml_str_from_compare(call_str))
            save_logs_of_logging_call_xml(call_xml, LogChangeType.ADDED_INSIDE_METHOD, file_diff.b_path, head_commit_db, method_name)

    for mapping in method_mapping_list:
        change_from = _get_code_text_from_compare(mapping[0])
        change_to = _get_code_text_from_compare(mapping[1])
        if change_from != change_to:
            # True Update
            logging_method_parent_xml = etree.fromstring(_get_code_xml_str_from_compare(mapping[0]))
            logging_method_head_xml = etree.fromstring(_get_code_xml_str_from_compare(mapping[1]))
            update_type = None
            method_updated_logging_loc += 1
            if not head_commit_db.is_merge_commit:
                call_name = codetransform.get_method_call_name(logging_method_head_xml)
                if '.' in call_name:
                    verbosity = call_name.split('.')[-1]
                else:
                    verbosity = call_name
                _, verbosity_type = metrics.get_log_content_component(change_to)
                argument_type = get_logging_argument_type(logging_method_head_xml)
                log = Log.create(commit=head_commit_db, file_path=file_diff.b_path, embed_method=method_name,
                                 change_type=LogChangeType.UPDATED, content=change_to, content_update_from=change_from,
                                 verbosity=verbosity, verbosity_type=verbosity_type, argument_type=argument_type, update_type=update_type)
                log.update_type = metrics.get_log_update_detail(log)
                log.is_consistent_update = is_log_consistent_update(log)
                log.save()

    return method_added_logging_loc, method_deleted_logging_loc, method_updated_logging_loc


def _get_code_xml_str_from_compare(xml_str):
    return xml_str.split('#', 1)[1]


def _get_code_text_from_compare(xml_str):
    return codetransform.transform_xml_str_to_code(_get_code_xml_str_from_compare(xml_str))


# def get_logging_update_type(logging_method_parent, logging_method_head) -> str:
#     update_type = ''
#     caller_change = get_logging_caller_change(logging_method_parent, logging_method_head)
#     argument_change = get_logging_parameter_change(logging_method_parent, logging_method_head)
#
#     if caller_change is not None and argument_change is not None:
#         update_type = str(caller_change) + '+' + str(argument_change)
#     elif caller_change is not None:
#         update_type = str(caller_change)
#     elif argument_change is not None:
#         update_type = str(argument_change)
#
#     return update_type


def get_logging_caller_change(method_parent, method_head) -> LogUpdateType:
    result = None
    call_name_parent = codetransform.get_method_call_name(method_parent)
    call_name_head = codetransform.get_method_call_name(method_head)
    if call_name_parent != call_name_head:
        if '.' in call_name_parent and '.' in call_name_head:
            caller_parent_list = call_name_parent.split('.', 1)
            caller_head_list = call_name_head.split('.', 1)
            if caller_parent_list[0] == caller_head_list[0]:
                if caller_parent_list[1] != caller_head_list[1]:
                    result = LogUpdateType.UPDATED_VERBOSITY
            else:
                result = LogUpdateType.UPDATED_LOGGING_METHOD
        else:
            result = LogUpdateType.UPDATED_LOGGING_METHOD

    return result


def get_logging_parameter_change(method_parent, method_head) -> LogUpdateType:
    result = None
    arguments_parent = codetransform.get_logging_argument(method_parent)
    arguments_head = codetransform.get_logging_argument(method_head)

    if len(arguments_parent) == len(arguments_head):
        is_text_change = False
        is_var_change = False
        is_sim_change = False
        for index in range(len(arguments_parent)):
            argument_parent = arguments_parent[index]
            argument_head = arguments_head[index]
            text_argument_parent = argument_parent[0]
            var_argument_parent = argument_parent[1]
            sim_argument_parent = argument_parent[2]
            text_argument_head = argument_head[0]
            var_argument_head = argument_head[1]
            sim_argument_head = argument_head[2]

            if _check_if_list_change(text_argument_parent, text_argument_head):
                is_text_change = True
            if _check_if_list_change(var_argument_parent, var_argument_head):
                is_var_change = True
            if _check_if_list_change(sim_argument_parent, sim_argument_head):
                is_sim_change = True

        if is_text_change and not is_var_change and not is_sim_change:
            result = LogUpdateType.UPDATED_TEXT
        elif is_text_change and is_var_change and not is_sim_change:
            result = LogUpdateType.UPDATED_TEXT_VAR
        elif is_text_change and not is_var_change and is_sim_change:
            result = LogUpdateType.UPDATED_TEXT_SIM
        elif is_text_change and is_var_change and is_sim_change:
            result = LogUpdateType.UPDATED_TEXT_VAR_SIM
        elif is_var_change and not is_text_change and not is_sim_change:
            result = LogUpdateType.UPDATED_VAR
        elif is_var_change and not is_text_change and is_sim_change:
            result = LogUpdateType.UPDATED_VAR_SIM
        elif is_sim_change and not is_text_change and not is_var_change:
            result = LogUpdateType.UPDATED_SIM
    elif len(arguments_parent) > len(arguments_head):
        result = LogUpdateType.ARGUMENT_DELETED
    elif len(arguments_parent) < len(arguments_head):
        result = LogUpdateType.ARGUMENT_ADDED

    return result


def _check_if_list_change(list_a, list_b):
    result = False
    if len(list_a) != len(list_b):
        result = True
    else:
        for index in range(len(list_a)):
            if etree.tostring(list_a[index]) != etree.tostring(list_b[index]):
                result = True
                break

    return result


def get_logging_argument_type(method_xml) -> LogArgumentType:
    result = None
    arguments = codetransform.get_logging_argument(method_xml)
    contains_text = False
    contains_var = False
    contains_sim = False
    for argument in arguments:
        if len(argument[0]) > 0:
            contains_text = True
        if len(argument[1]) > 0:
            contains_var = True
        if len(argument[2]) > 0:
            contains_sim = True

    if contains_text and not contains_var and not contains_sim:
        result = LogArgumentType.TEXT_ONLY
    elif contains_text and contains_var and not contains_sim:
        result = LogArgumentType.TEXT_VAR
    elif contains_text and not contains_var and contains_sim:
        result = LogArgumentType.TEXT_SIM
    elif contains_text and contains_var and contains_sim:
        result = LogArgumentType.TEXT_VAR_SIM
    elif contains_var and not contains_text and not contains_sim:
        result = LogArgumentType.VAR_ONLY
    elif contains_var and not contains_text and contains_sim:
        result = LogArgumentType.VAR_SIM
    elif contains_sim and not contains_text and not contains_var:
        result = LogArgumentType.SIM_ONLY

    return result


def get_complement_of_a_in_b(a_collection, b_collection):
    result = []
    for item in b_collection:
        if item not in a_collection:
            result.append(item)
    return result


def detect_project(repo: Repo, need_pull: bool, until_date: datetime):
    if repo.url and repo.url in config.REPO_URL_BLACK_LIST:
        return

    if not urlhelper.url_is_alive(repo.url):
        return

    logger.info('processing {}'.format(repo.app_id))

    path = config.get_repo_local_path_with_app_id(repo.app_id)

    if need_pull:
        githelper.refresh_and_pull_git_repo(path)
    else:
        githelper.refresh_git_repo(path)

    update_repo_summary(repo)

    if not repo.is_repo_valid():
        return

    commit_list = githelper.get_all_commits(path)
    git_repo = githelper.get_project_repository(path)

    for i in range(0, len(commit_list)):
        head_commit_sha = commit_list[i]
        head_commit = git_repo.commit(head_commit_sha)
        if until_date and head_commit.committed_date < until_date.timestamp():
            repo.analyzed_date = datetime.now()
            repo.save()
            return

        is_merge_commit = False
        logger.info('current commit: {}'.format(head_commit_sha))
        if head_commit.parents:
            if len(head_commit.parents) > 1:
                is_merge_commit = True

            head_commit_db = Commit.get_or_create(repo=repo, commit_id=head_commit_sha)[0]
            head_commit_db.is_merge_commit = is_merge_commit
            if i == 0:
                head_commit_db.sloc = repo.sloc
                head_commit_db.logging_loc = repo.logging_loc

            for parent_commit in head_commit.parents:
                parent_commit_sha = parent_commit.hexsha
                diff = githelper.get_diff_between_commits(parent_commit, head_commit)
                head_commit_db.parent_commit_id = parent_commit_sha
                parent_commit_db = Commit.get_or_create(repo=repo, commit_id=parent_commit_sha)[0]
                if _is_commit_analyzed(head_commit_db) and _is_commit_analyzed(parent_commit_db):
                    continue

                sloc = head_commit_db.sloc
                logging_loc = head_commit_db.logging_loc
                sloc_delta, logging_loc_delta = diff_inspector(git_repo, diff, head_commit_db)
                sloc -= sloc_delta
                logging_loc -= logging_loc_delta
                parent_commit_db.sloc = sloc
                parent_commit_db.logging_loc = logging_loc
                parent_commit_db.save()
        else:
            # Initial Commit
            diff = githelper.get_diff_of_initial_commit(git_repo, head_commit)
            head_commit_db = Commit.get_or_create(repo=repo, commit_id=head_commit_sha)[0]
            if not _is_commit_analyzed(head_commit_db):
                diff_inspector(git_repo, diff, head_commit_db)


def _is_commit_analyzed(commit: Commit):
    return commit.code_churn is not None


def update_repo_summary(repo: Repo):
    path = config.get_repo_local_path_with_app_id(repo.app_id)

    local_last_commit_date = githelper.get_last_commit_date(path)
    if repo.last_commit_date is None or local_last_commit_date > repo.last_commit_date:
        repo.files_num = githelper.get_files_num(path)
        repo.commits_num = githelper.get_commits_num(path)
        repo.last_commit_date = local_last_commit_date
        repo.first_commit_date = githelper.get_first_commit_date(path)
        repo.authors_num = githelper.get_authors_num(path)
        repo.sloc = getloc.get_java_sloc(path)
        repo.logging_loc = getloc.get_logging_loc_of_repo(path)
        repo.save()


def get_verbosity_level_distribution_of_repo(repo: Repo):
    path = config.get_repo_local_path_with_app_id(repo.app_id)
    githelper.refresh_git_repo(path)
    logging_calls_xml = codetransform.get_logging_calls_xml_of_repo(path)
    verbose = 0
    debug = 0
    info = 0
    warn = 0
    error = 0
    other = 0
    for call_xml in logging_calls_xml:
        call_text = codetransform.transform_xml_str_to_code(etree.tostring(call_xml).decode('utf-8'))
        _, verbosity_type = metrics.get_log_content_component(call_text)
        if verbosity_type == LogVerbosityType.VERBOSE:
            verbose += 1
        elif verbosity_type == LogVerbosityType.DEBUG:
            debug += 1
        elif verbosity_type == LogVerbosityType.INFO:
            info += 1
        elif verbosity_type == LogVerbosityType.WARN:
            warn += 1
        elif verbosity_type == LogVerbosityType.ERROR:
            error += 1
        else:
            other += 1

    return verbose, debug, info, warn, error, other


def get_loc_of_all_commits_of_repo(repo: Repo):
    path = config.get_repo_local_path_with_app_id(repo.app_id)
    githelper.refresh_git_repo(path)
    git_repo = githelper.get_project_repository(path)

    if not repo.is_repo_valid():
        return

    commits_db = repo.get_non_merge_commits()
    for commit_db in commits_db:
        commit_id = commit_db.commit_id
        parent_commit_id = commit_db.parent_commit_id
        githelper.checkout_commit(git_repo, commit_id)
        commit_db.sloc = getloc.get_java_sloc(path)
        commit_db.logging_loc = getloc.get_logging_loc_of_repo(path)
        if parent_commit_id:
            commit_db.code_churn = githelper.get_code_churn_between_commits(path, parent_commit_id, commit_id)
        commit_db.save()

    githelper.refresh_git_repo(path)


def is_log_consistent_update(log: Log):
    """ THIS METHOD SHOULD BE CALLED AFTER LOG UPDATE_TYPE IS DETERMINED """
    if log.update_type is None:
        return None

    if not (LogUpdateType.ADDED_VAR in log.update_type or
            LogUpdateType.DELETED_VAR in log.update_type or
            LogUpdateType.REPLACED_VAR in log.update_type):
        return False

    commit = log.commit
    repo = commit.repo
    repo_path = config.get_repo_local_path_with_app_id(repo.app_id)
    commit_id = commit.commit_id
    parent_commit_id = commit.parent_commit_id
    file_path = log.file_path
    output = shellhelper.run("git diff -U0 {} {} -- '{}' | grep '^[+]' | grep -Ev '^(--- a/|\+\+\+ b/)'".format
                             (parent_commit_id, commit_id, file_path), cwd=repo_path)
    lines = output.splitlines()
    log_xml_obj = codetransform.transform_log_str_to_xml_obj(log.content)
    all_vars_in_log = codetransform.get_all_var_str_in_call(log_xml_obj)
    if all_vars_in_log is None:
        return False
    all_vars_set = set(all_vars_in_log)
    is_consistent_update = False
    for line in lines:
        line = line[1:].strip()
        if line in log.content:
            break
        if line.startswith('//') or line.startswith('/*'):
            continue
        if line.endswith(';') and '=' in line:
            possible_var_statement = line.split('=')[0]
            if len(possible_var_statement) > 0 and '"' not in possible_var_statement:
                # '=' is not in a string or comment
                possible_var = possible_var_statement.split()[-1]
                if possible_var in all_vars_set:
                    is_consistent_update = True
                    break
        elif line.endswith('{'):
            possible_var_statement = line.replace('(', ' ').replace(')', ' ').replace(',', ' ').split()
            if len(all_vars_set.intersection(set(possible_var_statement))) > 0:
                is_consistent_update = True
                break

    return is_consistent_update


if __name__ == '__main__':
    pass
