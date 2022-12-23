#!/usr/bin/env python3
#-*- coding: utf-8 -*-

#@Author : Yi(Joy) Zeng


import datetime
import statistics

from openpyxl import load_workbook
from . import logchange


def get_xlsx_content(file_path):
    """
    return log change xlsx file content.
    :param file_path:
    :return: [['parent_commit', 'current_commit', 'file_path', 'method', 'change_type', 'argument_type', 'change_from', 'change_to', 'modified_type', 'parent_commit_date', 'current_commit_date', 'parent_author_date', 'current_author_date',  'author']]
    """
    workbook = load_workbook(file_path)
    first_sheet_name = workbook.get_sheet_names()[0]
    worksheet = workbook.get_sheet_by_name(first_sheet_name)

    rows = worksheet.rows
    content = []
    for row in rows:
        line = [col.value for col in row]
        content.append(line)

    return content


def get_log_description_with_line(line):
    file_path = line[2]
    method = line[3]
    change_from = line[6]
    change_to = line[7]
    current_commit_date = line[10]
    current_author_date = line[12]
    current_commit_id = line[1]
    return file_path, method, change_from, change_to, current_commit_date, current_author_date, current_commit_id


def find_from_candidate_of_line_info(target_line_info, source_lines):
    from_candidates = []
    compare_candidate = None
    for source_line in source_lines:
        source_line_info = get_log_description_with_line(source_line)
        if source_line_info[3].replace(' ', '') == target_line_info[2].replace(' ', ''):
            source_line_datetime = get_commit_datetime_of_line_info(source_line_info)
            target_line_datetime = get_commit_datetime_of_line_info(target_line_info)
            if source_line_datetime < target_line_datetime:
                from_candidates.append(source_line_info)

    if len(from_candidates) > 0:
        for candidate in from_candidates:
            candidate_file_name = candidate[0].split('/')[-1]
            candidate_method = candidate[1].split('(')[0]
            target_info_file_name = target_line_info[0].split('/')[-1]
            target_info_method = target_line_info[1].split('(')[0]
            if candidate_file_name == target_info_file_name and candidate_method == target_info_method:
                compare_candidate = candidate
                break

        if compare_candidate is None:
            # Poor workaround for file renaming situation, maybe should use git follow.
            for candidate in from_candidates:
                candidate_method = candidate[1].split('(')[0]
                target_info_method = target_line_info[1].split('(')[0]
                if candidate_method == target_info_method:
                    compare_candidate = candidate
                    break

        if compare_candidate is None:
            # Poor workaround for method renaming situation, maybe should use git follow.
            for candidate in from_candidates:
                candidate_file_name = candidate[0].split('/')[-1]
                target_info_file_name = target_line_info[0].split('/')[-1]
                if candidate_file_name == target_info_file_name:
                    compare_candidate = candidate
                    break

    return compare_candidate


def get_commit_datetime_of_line_info(line_info):
    time_str = line_info[4]
    return _get_datetime_of_time_str(time_str)


def get_author_datetime_of_line_info(line_info):
    time_str = line_info[5]
    return _get_datetime_of_time_str(time_str)


def _get_datetime_of_time_str(time_str):
    time_format = '%Y-%m-%d %H:%M:%S%z'
    datetime_str = time_str[:-3] + time_str[-2:]
    datetime_obj = datetime.datetime.strptime(datetime_str, time_format)
    return datetime_obj


def check_logging_age(file_path):
    content = get_xlsx_content(file_path)
    deleted_inside_method_lines = list(filter(lambda x: x[4] == logchange.DELETED_INSIDE_METHOD, content))
    modified_lines = list(filter(lambda x: x[4] == logchange.UPDATED, content))
    added_lines = list(filter(lambda x: x[4].startswith('ADDED'), content))

    not_found_count = 0
    deleted_count = len(deleted_inside_method_lines)
    found_count = 0
    total_age_seconds = 0
    age_list = []

    for deleted_line in deleted_inside_method_lines:
        deleted_info = get_log_description_with_line(deleted_line)

        tmp_candidate = deleted_info
        root_modifed_candidate = None
        compared_to_lines = modified_lines
        while tmp_candidate is not None:
            root_modifed_candidate = tmp_candidate
            tmp_candidate = find_from_candidate_of_line_info(root_modifed_candidate, compared_to_lines)

        compare_candidate = root_modifed_candidate

        added_from = find_from_candidate_of_line_info(compare_candidate, added_lines)
        if added_from is None:
            # print('no added line found for :', compare_candidate)
            not_found_count += 1
        else:
            delete_date = get_commit_datetime_of_line_info(deleted_info)
            added_date = get_commit_datetime_of_line_info(added_from)
            age = delete_date - added_date
            # if age.total_seconds() < 60:
            #     continue
            age_seconds = age.total_seconds()
            found_count += 1
            total_age_seconds += age_seconds
            age_list.append(age_seconds)
            print(str(datetime.timedelta(seconds=age_seconds)))

    print('not found count ', not_found_count)
    print('deleted count ', deleted_count)
    print('found count ', found_count)
    print('average age seconds ', str(datetime.timedelta(seconds=total_age_seconds / found_count)))

    print('mean:', str(datetime.timedelta(seconds=statistics.mean(age_list))))
    print('median:', str(datetime.timedelta(seconds=statistics.median(age_list))))
    print('max:', str(datetime.timedelta(seconds=max(age_list))))
    print('min:', str(datetime.timedelta(seconds=min(age_list))))
    # print('variance:', str(datetime.timedelta(seconds=statistics.variance(age_list))))
    print('standard deviation:', str(datetime.timedelta(seconds=statistics.stdev(age_list))))


def check_logging_modification(output_path_str, modified_lines):
    same_text_count = 0
    verbosity_change_count = 0
    logging_method_change_count = 0
    total_modified_count = len(modified_lines)
    current_index = 0
    for modified_line in modified_lines:

        modified_info = get_log_description_with_line(modified_line)
        change_from = modified_info[2]
        change_to = modified_info[3]
        if change_from.replace(' ', '') == change_to.replace(' ', ''):
            same_text_count += 1
            output_data(output_path_str, ';'.join(modified_line) + ';a9')
        else:
            modified_type = modified_line[8]
            if modified_type == logchange.VERBOSITY_UPDATED:
                verbosity_change_count += 1
                output_data(output_path_str, ';'.join(modified_line) + ';a1')
            elif modified_type == logchange.LOGGING_METHOD_MODIFIED:
                logging_method_change_count += 1
                output_data(output_path_str, ';'.join(modified_line) + ';a10')
            else:
                hint = '''
                Please select modification detail type.
                Consistent update:
                    c1. condition expression
                    c2. variable declaration
                    c3. feature method
                    c4. class attribute
                    c5. variable assignment
                    c6. string invocation method
                    c7. method parameter
                    c8. exception condition
                
                After-thought update:
                    a1. verbosity
                    a2. dynamic content: variable
                    a3. dynamic content: string invocation method
                    a4. static text: add dynamic
                    a5. static text: update dynamic 
                    a6. static text: delete redundant information
                    a7. static text: spell/grammer
                    a8. static text: fixing misleading information
                    a9. static text: format & style change
                    a10. logging method invocation
                    a11. multiple change
                '''

                print('Already processed count: ', current_index, ' total count: ', total_modified_count)
                print(change_from)
                print(change_to)
                input_type = input(hint)
                output_data(output_path_str, ';'.join(modified_line) + ';' + input_type)
                print('\n')
            current_index += 1

    print('same text count', same_text_count)
    print('verbosity change count ', verbosity_change_count)
    print('logging method change count ', logging_method_change_count)
    print('total modified count ', total_modified_count)


def get_logging_method_modification(modified_lines):
    method_modified_lines = list(filter(lambda x: x[8] == logchange.LOGGING_METHOD_MODIFIED, modified_lines))
    print('logging method change count: ', len(method_modified_lines))
    for modified_line in method_modified_lines:
        modified_info = get_log_description_with_line(modified_line)
        method_from = modified_info[2].split('(')[0]
        method_to = modified_info[3].split('(')[0]


def output_data(file_path, content):
    with open(file_path, 'a') as writer:
        print(content, file=writer)


def get_statistics_result(data_list):
    pass


if __name__ == '__main__':
    # file_path = '../logchange_googleio.xlsx'
    file_path = '../logchange_wordpress.xlsx'

    check_logging_age(file_path)

    # content = get_xlsx_content(file_path)
    # modified_lines = list(filter(lambda x: x[4] == MODIFIED, content))
    # output_path = file_path.rsplit('.', 1)[0] + '_modification_detail.csv'
    # if os.path.exists(output_path):
    #     print('output_file exist, please delete it first')
    # else:
    #     title_str = 'parent_commit;current_commit;file_path;method;change_type;argument_type;change_from;change_to;modified_type;parent_committed_datetime;current_committed_datetime;parent_authored_datetime;current_authored_datetime;author;modification_detail'
    #     output_data(output_path, title_str)
    #     check_logging_modification(output_path, modified_lines)






