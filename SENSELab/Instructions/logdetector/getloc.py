#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng


import re
from logdetector.utils import shellhelper
from logdetector import codetransform


class LOC(object):
    files_num = 0
    blank_num = 0
    comment_num = 0
    code_num = 0

    def __init__(self, files_num=0, blank_num=0, comment_num=0, code_num=0):
        self.files_num = files_num
        self.blank_num = blank_num
        self.comment_num = comment_num
        self.code_num = code_num


def get_java_sloc(path: str, commit_id=None):
    return get_java_loc(path, commit_id).code_num


def get_java_loc(path: str, commit_id=None):
    if commit_id is None:
        output = shellhelper.run("cloc --include-lang=Java '{}'".format(path))
    else:
        output = shellhelper.run("cloc --include-lang=Java '{}' {}".format(path, commit_id), cwd=path)
    pattern = '.*Java.*'
    m = re.search(pattern, output)
    result = LOC()
    if m is not None:
        line = m.group(0)
        result = _convert_cloc_line_to_object(line)

    return result


def get_java_loc_diff(old_path: str, new_path: str):
    output = shellhelper.run("cloc --diff --diff-timeout 1000 '{}' '{}'".format(old_path, new_path))
    pattern = '.*Java(\s.*){4}'
    m = re.search(pattern, output)
    same = LOC()
    modified = LOC()
    added = LOC()
    removed = LOC()

    if m is not None:
        lines = m.group(0).split('\n')
        lines.pop(0)
        for line in lines:
            line_type = line.split()[0]
            loc_detail = _convert_cloc_line_to_object(line)
            if line_type == 'same':
                same = loc_detail
            elif line_type == 'modified':
                modified = loc_detail
            elif line_type == 'added':
                added = loc_detail
            elif line_type == 'removed':
                removed = loc_detail

    return {
        'same': same,
        'modified': modified,
        'added': added,
        'removed': removed
    }


def _convert_cloc_line_to_object(line) -> LOC:
    split_line = line.strip().split()
    files_num = int(split_line[1])
    blank_num = int(split_line[2])
    comment_num = int(split_line[3])
    code_num = int(split_line[4])
    return LOC(files_num, blank_num, comment_num, code_num)


def get_logging_loc_of_repo(path: str):
    return len(codetransform.get_logging_calls_xml_of_repo(path))


def get_logging_loc_of_file(path: str):
    return len(codetransform.get_logging_calls_xml_of_file(path))

