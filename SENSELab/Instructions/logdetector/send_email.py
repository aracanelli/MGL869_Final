#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng


import yagmail
from logdetector import config


def send_email(to, subject, contents, cc=None):
    yag = yagmail.SMTP(config.EMAIL_SENDER)
    yag.send(to=to, subject=subject, contents=contents, cc=cc)


def register(address, password):
    yagmail.register(address, password)
