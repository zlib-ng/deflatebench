""" benchmark.py -- Functionality related to running benchmarks

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import os
import sys
import time
from collections import namedtuple

from . import util

from .cli import printnn

# Simple usleep function
usleep = lambda x: time.sleep(x/1000000.0)

def printfile(level, filename):
    ''' Prints formatted information about file '''
    filesize = os.path.getsize(filename)
    print(f"Level {level}: {filename} {filesize/1024/1024:6.1f} MiB  {filesize:12,} B")

def parse_levels(level_string):
    ''' Parse string containing comma-separated levels or level ranges '''
    if not level_string or not level_string.strip():
        raise ValueError("Levels string is empty")
    levels = set()

    try:
        for part in level_string.split(','):
            part = part.strip()
            if not part:
                continue

            if '-' in part:
                start, end = part.split('-', 1)
                start, end = int(start), int(end)
                if start > end:
                    start, end = end, start
                levels.update(range(start, end + 1))
            else:
                levels.add(int(part))
    except ValueError as exc:
        raise ValueError(f"Invalid level: '{part}'") from exc

    return sorted(levels)

def run_timed(command, env, timefile, timemode, outfile):
    ''' Run command and return the elapsed cputime (or realtime if unavailable) '''
    starttime = time.perf_counter()
    util.runcommand(command, env=env, output=outfile)

    if timemode == 'python':
        return time.perf_counter() - starttime

    return util.parse_timefile(timefile)

def run_tests(testconfig):
    cfg = util.dict_to_namedt(testconfig)
    skipverify = cfg.skipverify

    # Prepare multilevel results arrays
    result_comp, result_decomp = dict(), dict()
    for level in cfg.levels:
        result_comp[level] = []
        result_decomp[level] = []

    # Run tests and record results
    for run in range(1, cfg.runs + 1):
        if run != 1:
            skipverify = True

        print(f"Starting run {run} of {cfg.runs}")
        for level in cfg.levels:
            compsize,comptime,decomptime,hashfail = run_test(cfg, level, skipverify)
            if hashfail != 0:
                print(f"ERROR: level {level} failed crc checking")
            if cfg.do_compress:
                result_comp[level].append( [compsize,comptime] )
            if cfg.do_decompress:
                result_decomp[level].append( [compsize,decomptime] )

    return result_comp, result_decomp

def run_test(cfg, level, skipverify):
    ''' Run benchmark and tests for current compression level '''
    # Prepare tempfiles
    hashfail, comptime, decomptime = 0, 0, 0
    env = util.get_env(True)
    orighash = cfg.tempfiles[level]['hash']

    testfile = cfg.tempfiles[level]['filename']
    compfile = os.path.join(cfg.temp_path, 'zlib-testfil.gz')
    decompfile = os.path.join(cfg.temp_path, 'zlib-testfil.raw')

    sys.stdout.write(f"Testing level {level}: ")
    if sys.platform != 'win32':
        os.sync()

    # Compress
    if cfg.do_compress:
        printnn('c')
        usleep(10)
        comptime = run_timed(f"{cfg.cmdprefix} {cfg.testtool} -{level} -c {testfile}", env, cfg.timefile, cfg.timemode, compfile)
    else:
        # compression disabled, just pass the file on to decompress
        compfile = testfile

    compsize = os.path.getsize(compfile)

    # Decompress
    if cfg.do_decompress or not skipverify:
        printnn('d')
        usleep(10)
        decomptime = run_timed(f"{cfg.cmdprefix} {cfg.testtool} -d -c {compfile}", env, cfg.timefile, cfg.timemode, decompfile)

        if not skipverify:
            ourhash = util.hashfile(decompfile)
            if ourhash != orighash:
                print(f"{orighash} != {ourhash}")
                hashfail = 1

        os.unlink(decompfile)

    # Validate using gunzip
    if cfg.do_compress and not skipverify:
        printnn('v')
        util.runcommand(f"gunzip -c {compfile}", output=decompfile)

        gziphash = util.hashfile(decompfile)
        if gziphash != orighash:
            print(f"{orighash} != {gziphash}")
            hashfail = 1

        os.unlink(decompfile)

    # Cleanup
    if os.path.exists(cfg.timefile):
        os.unlink(cfg.timefile)
    if cfg.do_compress:
        os.unlink(compfile)

    comppct = float(compsize*100)/cfg.tempfiles[level]['origsize']
    if cfg.do_compress:
        printnn(f" {comptime:7.4f}s")
    if cfg.do_decompress:
        printnn(f" {decomptime:7.4f}s")
    print(f" {compsize:15,}B {comppct:7.3f}%")

    return compsize,comptime,decomptime,hashfail
