#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author : Yi(Joy) Zeng

import logging


logging.basicConfig(filename='detector.log', filemode='a', format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
logging.getLogger(__name__).addHandler(logging.NullHandler())
