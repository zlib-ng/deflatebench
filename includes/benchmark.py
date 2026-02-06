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

def printfile(level, filename, comment=None):
    ''' Prints formatted information about file '''
    filesize = os.path.getsize(filename)
    printnn(f"Level {level}: {filename} {filesize/1024/1024:6.1f} MiB  {filesize:12,} B")
    if comment:
        printnn(f" {comment}")
    print('')

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
            compsize,comptime,decompsize,decomptime,hashfail = run_test(cfg, level, skipverify)
            if hashfail != 0:
                print(f"ERROR: level {level} failed crc checking")
            if cfg.do_compress:
                result_comp[level].append( [compsize,comptime] )
            if cfg.do_decompress:
                result_decomp[level].append( [decompsize,decomptime] )

    return result_comp, result_decomp

def run_test(cfg, level, skipverify):
    ''' Run benchmark and tests for current compression level '''
    # Prepare tempfiles
    hashfail, compsize, decompsize, comptime, decomptime = [0] * 5
    env = util.get_env(True)
    hash_comp = cfg.tempfiles[level]['hash_comp']
    hash_decomp = cfg.tempfiles[level]['hash_decomp']

    compress_in = cfg.tempfiles[level]['filename_comp']
    compress_out = os.path.join(cfg.temp_path, 'zlib-testfil.gz')

    if cfg.tempfiles[level]['filename_decomp'] is None:
        decompress_in = compress_out
    else:
        decompress_in = cfg.tempfiles[level]['filename_decomp']
    decompress_out = os.path.join(cfg.temp_path, 'zlib-testfil.raw')

    sys.stdout.write(f"Testing level {level}: ")
    if sys.platform != 'win32':
        os.sync()

    # Compress
    if cfg.do_compress:
        printnn('c')
        usleep(10)
        comptime = run_timed(f"{cfg.cmdprefix} {cfg.testtool} -{level} -c {compress_in}", env, cfg.timefile, cfg.timemode, compress_out)
        compsize = os.path.getsize(compress_out)

    # Decompress
    if cfg.do_decompress:
        printnn('d')
        usleep(10)
        decompsize = os.path.getsize(decompress_in)
        decomptime = run_timed(f"{cfg.cmdprefix} {cfg.testtool} -d -c {decompress_in}", env, cfg.timefile, cfg.timemode, decompress_out)

        if not skipverify:
            ourhash = util.hashfile(decompress_out)
            if ourhash != hash_decomp:
                print(f"\ndecompress: {hash_decomp} != {ourhash}")
                hashfail = 1

        os.unlink(decompress_out)

    # Validate using gunzip
    if cfg.do_compress and not skipverify:
        printnn('v')
        util.runcommand(f"gunzip -c {compress_out}", output=decompress_out)

        gziphash = util.hashfile(decompress_out)
        if gziphash != hash_comp:
            print(f"\nverify: {hash_comp} != {gziphash}")
            hashfail = 1

        os.unlink(decompress_out)

    # Cleanup
    if os.path.exists(cfg.timefile):
        os.unlink(cfg.timefile)
    if cfg.do_compress:
        os.unlink(compress_out)

    if cfg.do_compress:
        comppct = float(compsize*100)/cfg.tempfiles[level]['origsize_comp']
        printnn(f"   comp: {comptime:.4f}s {compsize}B {comppct:.3f}%")
    if cfg.do_decompress:
        decomppct = float(decompsize*100)/cfg.tempfiles[level]['origsize_decomp']
        printnn(f"   decomp: {decomptime:.4f}s {decompsize}B {decomppct:.3f}%")
    print('')

    return compsize,comptime,decompsize,decomptime,hashfail
