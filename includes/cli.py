""" cli.py -- Helperfunctions for formatting cli output.

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import re
import sys

# ANSI color codes
BLUE = '\033[34m'
GREEN = '\033[32m'
RED = '\033[31m'
BRIGHT = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'

strip_ANSI_regex = re.compile(r"""
    \x1b     # literal ESC
    \[       # literal [
    [;\d]*   # zero or more digits or semicolons
    [A-Za-z] # a letter
    """, re.VERBOSE).sub

def get_len(s):
    ''' Return string length excluding ANSI escape strings '''
    return len(strip_ANSI_regex("", s))

def padstr(instr, length, left=False):
    ''' Build string pad to length '''
    padstr = ' ' * (length - get_len(instr))
    return f"{padstr}{instr}" if not left else f"{instr}{padstr}"

def resultstr(result,totlen):
    ''' Build result string and pad to totlen'''
    tmpr = ( f"{BLUE}{result['mintime']:.4f}{RESET}"
             f"/{GREEN}{result['avgtime']:.4f}{RESET}"
             f"/{RED}{result['maxtime']:.4f}{RESET}"
             f"/{BRIGHT}{result['stddev']:.4f}{RESET}" )
    return padstr(tmpr, totlen)

def printnn(text):
    ''' Print without causing a newline '''
    sys.stdout.write(text)
    sys.stdout.flush()
