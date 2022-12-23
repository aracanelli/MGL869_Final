#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng

import csv
from urllib.request import urlopen
from datetime import datetime
from pathlib import Path
from logdetector.utils import filehelper
from logdetector.send_email import send_email
from logdetector import config


def get_changed_logs(input_file):
    changed_logs = {}
    # the input file is exported from postgres by executing
    #
    """
    select commit.repo_fk, commit.commit_id, commit.author_name, commit.author_email, commit.authored_date, commit.message, log.file_path, log.embed_method, log.change_type, log.content, log.content_update_from
    from log join commit on commit.id = log.commit_fk
    where author_email not like '%noreply.github.com%' and commit.authored_date > '2018-02-27' and log.change_type like 'ADD%'
    """

    p = Path(input_file)
    with p.open('r', encoding='utf-8') as f:
        next(f)
        reader = csv.reader(f)
        for row in reader:
            author_email = row[3]
            logs = changed_logs.get(author_email, [])
            logs.append(row)
            changed_logs[author_email] = logs

    return changed_logs


def generate_candidate_logs(input_file, output_file):
    filehelper.delete_if_exists(output_file)
    changed_logs = get_changed_logs(input_file)
    candidate_logs = []
    for author_email in changed_logs:
        candidate = None
        logs = changed_logs[author_email]
        sorted_logs = []
        for log in logs:
            change_type = log[8]
            if change_type == 'ADDED_INSIDE_METHOD':
                sorted_logs.append(log)
        for log in logs:
            change_type = log[8]
            if change_type == 'ADDED_WITH_METHOD':
                sorted_logs.append(log)
        for log in logs:
            change_type = log[8]
            if change_type == 'ADDED_WITH_FILE':
                sorted_logs.append(log)
        for log in logs:
            change_type = log[8]
            if change_type == 'UPDATED':
                sorted_logs.append(log)

        for log in sorted_logs:
            repo_url = log[0]
            commit_id = log[1]
            author_name = log[2]
            authored_date = log[4]
            commit_message = log[5]
            file_path = log[6]
            if filehelper.is_test_file(file_path):
                continue

            embed_method = log[7]
            change_type = log[8]
            content = log[9]
            content_update_from = log[10]

            if not candidate:
                candidate = log
            else:
                authored_datetime = datetime.strptime(authored_date+'00', '%Y-%m-%d %H:%M:%S%z')
                candidate_datetime = datetime.strptime(candidate[4]+'00', '%Y-%m-%d %H:%M:%S%z')
                if authored_datetime > candidate_datetime:
                    candidate = log

        if candidate:
            candidate_logs.append(candidate)

    header = 'repo_fk,commit_id,author_name,author_email,authored_date,message,file_path,embed_method,change_type,content,content_update_from'
    filehelper.append_line(header, output_file)
    for log in candidate_logs:
        line = ''
        for item in log:
            line += '"{}",'.format(item.replace('"', '""'))
        line = line[:-1]
        filehelper.append_line(line, output_file)


def get_repo_name(repo_url):
    response = urlopen(repo_url)
    return response.geturl().split('/')[-1]


def generate_email_content(input_file, existing_emails):
    p = Path(input_file)
    with p.open('r', encoding='utf-8') as f:
        next(f)
        reader = csv.reader(f)
        for log in reader:
            repo_url = log[0]
            repo_name = get_repo_name(repo_url)
            commit_id = log[1]
            author_name = log[2]
            author_email = log[3]
            authored_date = log[4]
            commit_message = log[5]
            file_path = log[6]
            embed_method = log[7]
            change_type = log[8]
            content = log[9]
            content_update_from = log[10]

            if author_email in existing_emails:
                continue

            email_body = """
Dear {},

I am a Master's student at Concordia University, Canada working on a research about mobile logging practices.
As part of my research, I found that you recently add a log statement on <b>{}</b> project:

    File path: <b>{}</b>
    Code:      <b>{};</b>

This is the GitHub link to the commit:
{}

Looking at the change, I am wondering if you could answer the following brief question:
    <b>Could you describe why did you add the log statement in this situation?</b>

You may find out more about previous studies in this area <a href=\"http://users.encs.concordia.ca/~shang/#publications\">here</a>. 
Your contribution to this research is appreciated.

Thank you in advance for your collaboration.

-- 
Yi(Joy) Zeng
Master's Student
Dept. of Computer Science and Software Engineering
Concordia University

""".format(author_name, repo_name,file_path, content, repo_url + '/commit/' + commit_id)
            print(author_email)
            print(email_body)
            should_send = input('Please review the content, press Y to send email, press else to skip\n')
            if should_send.lower() == 'y':
                send_email(author_email, 'Mobile Logging Research on {}'.format(repo_name), [email_body], config.EMAIL_CC)
            else:
                pass


def get_existing_author_emails(log_email_path):
    p = Path(log_email_path)
    emails = []
    with p.open('r', encoding='utf-8') as f:
        next(f)
        reader = csv.reader(f)
        for log in reader:
            author_email = log[3]
            status = log[11]
            if status != 'FP':
                emails.append(author_email)

    return emails


if __name__ == '__main__':
    candidate_logs_file = '../data/candidate_logs_from_07-11_to_07-18.csv'
    added_logs_file = '../data/added_logs_from_07-11_to_07-18.csv'

    generate_candidate_logs(added_logs_file, candidate_logs_file)

    log_email_path = '../data/log_emails.csv'
    existing_emails = get_existing_author_emails(log_email_path)
    generate_email_content(candidate_logs_file, existing_emails)
