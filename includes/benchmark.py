""" benchmark.py -- Functionality related to running benchmarks

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import os
import sys
import time

from . import cli
from . import util

# Simple usleep function
usleep = lambda x: time.sleep(x/1000000.0)

def runtest(testtool, temp_path, tempfiles, timefile, level, cmdprefix, skipdecomp, skipverify):
    ''' Run benchmark and tests for current compression level'''
    # Prepare tempfiles
    compfile = os.path.join(temp_path, 'zlib-testfil.gz')
    decompfile = os.path.join(temp_path, 'zlib-testfil.raw')

    hashfail, decomptime = 0,0
    testfile = tempfiles[level]['filename']
    orighash = tempfiles[level]['hash']

    env = util.get_env(True)

    sys.stdout.write(f"Testing level {level}: ")
    if sys.platform != 'win32':
        util.runcommand('sync')

    # Compress
    cli.printnn('c')
    usleep(10)
    starttime = time.perf_counter()
    testtool = os.path.realpath(testtool)

    util.runcommand(f"{cmdprefix} {testtool} -{level} -c {testfile}", env=env, output=compfile)
    if sys.platform != 'win32':
        comptime = util.parse_timefile(timefile)
    else:
        comptime = time.perf_counter() - starttime
    compsize = os.path.getsize(compfile)

    # Decompress
    if not skipdecomp or not skipverify:
        cli.printnn('d')
        usleep(10)
        starttime = time.perf_counter()
        util.runcommand(f"{cmdprefix} {testtool} -d -c {compfile}", env=env, output=decompfile)

        if sys.platform != 'win32':
            decomptime = util.parse_timefile(timefile)
        else:
            decomptime = time.perf_counter() - starttime

        if not skipverify:
            ourhash = util.hashfile(decompfile)
            if ourhash != orighash:
                print(f"{orighash} != {ourhash}")
                hashfail = 1

        os.unlink(decompfile)

    # Validate using gunzip
    if not skipverify:
        cli.printnn('v')
        util.runcommand(f"gunzip -c {compfile}", output=decompfile)

        gziphash = util.hashfile(decompfile)
        if gziphash != orighash:
            print(f"{orighash} != {gziphash}")
            hashfail = 1

        os.unlink(decompfile)

    if os.path.exists(timefile):
        os.unlink(timefile)
    os.unlink(compfile)

    comppct = float(compsize*100)/tempfiles[level]['origsize']
    cli.printnn(f" {comptime:7.4f} {decomptime:7.4f} {compsize:15,} {comppct:7.3f}%\n")

    return compsize,comptime,decomptime,hashfail
