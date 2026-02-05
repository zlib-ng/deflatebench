""" benchmark.py -- Functionality related to running benchmarks

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import os
import sys
import time

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

def runtest(testtool, timemode, do_compress, do_decompress, temp_path, tempfiles, timefile, level, cmdprefix, skipverify):
    ''' Run benchmark and tests for current compression level '''
    # Prepare tempfiles
    compfile = os.path.join(temp_path, 'zlib-testfil.gz')
    decompfile = os.path.join(temp_path, 'zlib-testfil.raw')

    hashfail, comptime, decomptime = 0, 0, 0
    testfile = tempfiles[level]['filename']
    orighash = tempfiles[level]['hash']

    env = util.get_env(True)
    testtool = os.path.realpath(testtool)

    sys.stdout.write(f"Testing level {level}: ")
    if sys.platform != 'win32':
        os.sync()

    # Compress
    if do_compress:
        printnn('c')
        usleep(10)
        comptime = run_timed(f"{cmdprefix} {testtool} -{level} -c {testfile}", env, timefile, timemode, compfile)
    else:
        # compression disabled, just pass the file on to decompress
        compfile = testfile

    compsize = os.path.getsize(compfile)

    # Decompress
    if do_decompress or not skipverify:
        printnn('d')
        usleep(10)
        decomptime = run_timed(f"{cmdprefix} {testtool} -d -c {compfile}", env, timefile, timemode, decompfile)

        if not skipverify:
            ourhash = util.hashfile(decompfile)
            if ourhash != orighash:
                print(f"{orighash} != {ourhash}")
                hashfail = 1

        os.unlink(decompfile)

    # Validate using gunzip
    if do_compress and not skipverify:
        printnn('v')
        util.runcommand(f"gunzip -c {compfile}", output=decompfile)

        gziphash = util.hashfile(decompfile)
        if gziphash != orighash:
            print(f"{orighash} != {gziphash}")
            hashfail = 1

        os.unlink(decompfile)

    # Cleanup
    if os.path.exists(timefile):
        os.unlink(timefile)
    if do_compress:
        os.unlink(compfile)

    comppct = float(compsize*100)/tempfiles[level]['origsize']
    if do_compress:
        printnn(f" {comptime:7.4f}s")
    if do_decompress:
        printnn(f" {decomptime:7.4f}s")
    print(f" {compsize:15,}B {comppct:7.3f}%")

    return compsize,comptime,decomptime,hashfail
