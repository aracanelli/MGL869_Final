#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng


from peewee import *
from playhouse.postgres_ext import DateTimeTZField
from logdetector import config


db = PostgresqlDatabase(config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD, host=config.DB_HOST, port=config.DB_PORT)


class BaseModel(Model):
    class Meta:
        database = db


class Repo(BaseModel):
    url = TextField(primary_key=True)
    app_id = CharField()
    name = CharField(null=True)
    authors_num = IntegerField(null=True)
    commits_num = IntegerField(null=True)
    files_num = BigIntegerField(null=True)
    last_commit_date = DateTimeTZField(null=True)
    first_commit_date = DateTimeTZField(null=True)
    sloc = BigIntegerField(null=True)
    logging_loc = BigIntegerField(null=True)
    analyzed_date = DateTimeTZField(null=True)

    def is_repo_valid(self):
        return (self.sloc > config.VALID_PROJECT_SLOC_THRESHOLD) and (self.url not in config.REPO_URL_BLACK_LIST)

    def get_non_merge_commits(self):
        return self.commits.where(Commit.is_merge_commit == False)


class Commit(BaseModel):
    repo = ForeignKeyField(Repo, db_column='repo_fk', related_name='commits', on_delete='CASCADE')
    commit_id = CharField()
    parent_commit_id = CharField(null=True)
    is_merge_commit = BooleanField(default=False)
    author_email = CharField(null=True)
    author_name = CharField(null=True)
    authored_date = DateTimeTZField(null=True)
    committer_email = CharField(null=True)
    committer_name = CharField(null=True)
    committed_date = DateTimeTZField(null=True)
    message = TextField(null=True)
    sloc = BigIntegerField(null=True)
    logging_loc = BigIntegerField(null=True)
    code_churn = BigIntegerField(null=True)
    logging_code_churn = BigIntegerField(null=True)


class Log(BaseModel):

    commit = ForeignKeyField(Commit, db_column='commit_fk', related_name='logs', on_delete='CASCADE')
    file_path = TextField()
    embed_method = TextField()
    change_type = CharField()
    content = TextField()
    update_type = CharField(null=True)
    content_update_from = TextField(null=True)
    verbosity = CharField(null=True)
    verbosity_type = CharField(null=True)
    argument_type = CharField(null=True)
    is_consistent_update = BooleanField(null=True)

    def is_type_added(self):
        return self.change_type == LogChangeType.ADDED_WITH_FILE or \
               self.change_type == LogChangeType.ADDED_WITH_METHOD or \
               self.change_type == LogChangeType.ADDED_INSIDE_METHOD

    def is_type_deleted(self):
        return self.change_type == LogChangeType.DELETED_WITH_FILE or \
               self.change_type == LogChangeType.DELETED_WITH_METHOD or \
               self.change_type == LogChangeType.DELETED_INSIDE_METHOD

    def is_type_updated(self):
        return self.change_type == LogChangeType.UPDATED


class LogChangeType(object):
    DELETED_WITH_FILE = 'DELETED_WITH_FILE'
    ADDED_WITH_FILE = 'ADDED_WITH_FILE'
    DELETED_WITH_METHOD = 'DELETED_WITH_METHOD'
    ADDED_WITH_METHOD = 'ADDED_WITH_METHOD'
    DELETED_INSIDE_METHOD = 'DELETED_INSIDE_METHOD'
    ADDED_INSIDE_METHOD = 'ADDED_INSIDE_METHOD'
    UPDATED = 'UPDATED'


class LogUpdateType(object):
    UPDATED_FORMAT = 'UPDATED_FORMAT'
    UPDATED_VERBOSITY = 'UPDATED_VERBOSITY'
    UPDATED_LOGGING_METHOD = 'UPDATED_LOGGING_METHOD'
    ADDED_TEXT = 'ADDED_TEXT'
    ADDED_VAR = 'ADDED_VAR'
    ADDED_SIM = 'ADDED_SIM'
    DELETED_TEXT = 'DELETED_TEXT'
    DELETED_VAR = 'DELETED_VAR'
    DELETED_SIM = 'DELETED_SIM'
    REPLACED_TEXT = 'REPLACED_TEXT'
    REPLACED_VAR = 'REPLACED_VAR'
    REPLACED_SIM = 'REPLACED_SIM'


class LogArgumentType(object):
    TEXT_ONLY = 'TEXT_ONLY'
    VAR_ONLY = 'VAR_ONLY'
    SIM_ONLY = 'SIM_ONLY'
    TEXT_VAR = 'TEXT_VAR'
    TEXT_SIM = 'TEXT_SIM'
    VAR_SIM = 'VAR_SIM'
    TEXT_VAR_SIM = 'TEXT_VAR_SIM'


class LogVerbosityType(object):
    VERBOSE = 'VERBOSE'
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARN = 'WARN'
    ERROR = 'ERROR'
