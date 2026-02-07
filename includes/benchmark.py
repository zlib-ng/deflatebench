""" benchmark.py -- Functionality related to running benchmarks

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import os
import sys
import shutil
import time
from collections import namedtuple

from . import util

from .cli import printnn

# Simple usleep function
usleep = lambda x: time.sleep(x/1000000.0)

def print_file(level, filename, comment=''):
    ''' Prints formatted information about file '''
    filesize = os.path.getsize(filename)
    print(f"Level {level}: {filename} {filesize/1024/1024:6.1f} MiB  {filesize:12,} B  {comment}")

def print_files(cfg, tempfiles, same_input=True, level_files=False):
    ''' Prints formatted information about files '''
    if not level_files and (same_input or not cfg.do_compress or not cfg.do_decompress):
        if cfg.do_compress:
            filename = tempfiles[cfg.levels[0]]['filename_comp']
        elif cfg.do_decompress:
            filename = tempfiles[cfg.levels[0]]['filename_decomp']
        print_file(cfg.levels, filename)
    elif not level_files:
        if cfg.do_compress:
            filename = tempfiles[cfg.levels[0]]['filename_comp']
            print_file(cfg.levels, filename, 'Compression')
        if cfg.do_decompress:
            filename = tempfiles[cfg.levels[0]]['filename_decomp']
            print_file(cfg.levels, filename, 'Decompression')
    else:
        if cfg.do_compress:
            for level in cfg.levels:
                filename = tempfiles[level]['filename_comp']
                if same_input:
                    print_file(level, filename)
                else:
                    print_file(level, filename, 'Compression')

        if cfg.do_decompress and not same_input:
            for level in cfg.levels:
                filename = tempfiles[level]['filename_decomp']
                print_file(level, filename, 'Decompression')
    print()

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

def get_empty_tempfiles(levels):
    tempfiles = dict()
    for level in levels:
        tempfiles[level] = dict()
        tempfiles[level]['filename_comp'] = None
        tempfiles[level]['filename_decomp'] = None
        tempfiles[level]['hash_comp'] = None
        tempfiles[level]['hash_decomp'] = None
        tempfiles[level]['origsize_comp'] = None
        tempfiles[level]['origsize_decomp'] = None
    return tempfiles

def prepare_singlemode(testconfig, cfgSingle):
    ''' Single mode, we use the same file for every level, but support separate files for compress/decompress '''
    cfg = util.dict_to_namedt(testconfig)
    tempfiles = get_empty_tempfiles(cfg.levels)

    # Same input file for compress + decompress?
    same_input_file = False
    if cfg.do_compress and cfgSingle.get('testfile_compress') == cfgSingle.get('testfile_decompress'):
        same_input_file = True

    printnn("Preparing tempfiles ")

    # Compress
    if cfg.do_compress:
        tmp_compress_in = os.path.join(cfg.temp_path, "deflatebench-comp.tmp")
        srcfile_comp = util.findfile(cfgSingle['testfile_compress'])
        shutil.copyfile(srcfile_comp,tmp_compress_in)
        compress_hash = util.hashfile(tmp_compress_in)
        compress_origsize = os.path.getsize(tmp_compress_in)
        printnn('.')

        # Set up tempfiles
        for level in cfg.levels:
            tempfiles[level]['filename_comp'] = tmp_compress_in
            tempfiles[level]['hash_comp'] = compress_hash
            tempfiles[level]['origsize_comp'] = compress_origsize

    # Decompress
    if cfg.do_decompress:
        if same_input_file:
            # Use the same file as compress
            tmp_decompress_in = None
            decompress_hash = compress_hash
            decompress_origsize = compress_origsize
        else: # Use separate files for compress and decompress benchmarks
            srcfile_decomp = util.findfile(cfgSingle['testfile_decompress'])
            decompress_hash = util.hashfile(srcfile_decomp)
            decompress_origsize = os.path.getsize(srcfile_decomp)

            # Prepare separate compressed files for each level of decompression benchmark
            for level in cfg.levels:
                tmp_decompress_in = os.path.join(cfg.temp_path, f"{os.path.basename(srcfile_decomp)}-{level}.gz")
                util.runcommand(f"{cfg.testtool} -{level} -c {srcfile_decomp}", output=tmp_decompress_in)
                tempfiles[level]['filename_decomp'] = tmp_decompress_in
                printnn('.')

        # Set up tempfiles
        for level in cfg.levels:
            if same_input_file:
                tempfiles[level]['filename_decomp'] = tmp_decompress_in
            tempfiles[level]['hash_decomp'] = decompress_hash
            tempfiles[level]['origsize_decomp'] = decompress_origsize
    print()

    # Print a bit of info about the selected levels and files
    print_files(cfg, tempfiles, same_input=same_input_file)
    print("Activated single file mode")

    return tempfiles

def prepare_genmode(testconfig, cfgGenComp, cfgGenDecomp):
    ''' Gen mode, generate per-level tempfiles. Support separate input files for compress/decompress. '''
    cfg = util.dict_to_namedt(testconfig)
    tempfiles = get_empty_tempfiles(cfg.levels)

    # Same input files for compress + decompress?
    same_input_file = False
    if cfg.do_compress and cfg.do_decompress:
        if cfgGenDecomp['srcFile'] is None or cfgGenComp['srcFile'] == cfgGenDecomp['srcFile']:
            same_input_file = True

    printnn("Generating tempfiles ")

    # Compress
    if cfg.do_compress:
        for level in cfg.levels:
            tmp_comp = os.path.join(cfg.temp_path, f"deflatebench-comp-{level}.tmp")
            util.generate_testfile(util.findfile(cfgGenComp['srcFile']), tmp_comp, cfgGenComp[str(level)])

            tempfiles[level]['filename_comp'] = tmp_comp
            tempfiles[level]['hash_comp'] = util.hashfile(tmp_comp)
            tempfiles[level]['origsize_comp'] = os.path.getsize(tmp_comp)
            printnn('.')

    # Decompress
    if cfg.do_decompress:
        for level in cfg.levels:
            if same_input_file:
                # Reuse compression input for this level
                tempfiles[level]['filename_decomp'] = None
                tempfiles[level]['hash_decomp'] = tempfiles[level]['hash_comp']
                tempfiles[level]['origsize_decomp'] = tempfiles[level]['origsize_comp']
            else:
                # Generate separate input file
                tmp_raw = os.path.join(cfg.temp_path, f"deflatebench-decomp-{level}.tmp")
                util.generate_testfile(util.findfile(cfgGenDecomp['srcFile']), tmp_raw, cfgGenDecomp[str(level)])

                # Compress per-level file
                tmp_decomp = os.path.join(cfg.temp_path, f"deflatebench-decomp-{level}.gz")
                util.runcommand(f"{cfg.testtool} -{level} -c {tmp_raw}", output=tmp_decomp)

                tempfiles[level]['filename_decomp'] = tmp_decomp
                tempfiles[level]['hash_decomp'] = util.hashfile(tmp_raw)
                tempfiles[level]['origsize_decomp'] = os.path.getsize(tmp_raw)
                os.unlink(tmp_raw)
            printnn('.')
    print()

    # Print a bit of info about the selected levels and files
    print_files(cfg, tempfiles, same_input=same_input_file, level_files=True)
    print("Activated generated file mode")

    return tempfiles

def prepare_multimode(testconfig, cfgMultiComp, cfgMultiDecomp):
    ''' Multi mode, use per-level input files. Support separate input files for compress/decompress. '''
    cfg = util.dict_to_namedt(testconfig)
    tempfiles = get_empty_tempfiles(cfg.levels)

    # Same input files for compress + decompress?
    if cfg.do_compress and cfg.do_decompress:
        same_input_file = True
        for level in cfg.levels:
            if cfgMultiDecomp[str(level)] and cfgMultiComp[str(level)] and cfgMultiDecomp[str(level)] != cfgMultiComp[str(level)]:
                same_input_file = False
    else:
        same_input_file = False

    printnn("Preparing tempfiles ")

    # Compress
    if cfg.do_compress:
        for level in cfg.levels:
            srcfile = util.findfile(cfgMultiComp[str(level)])
            tmp_comp = os.path.join(cfg.temp_path, f"deflatebench-comp-{level}.tmp")
            shutil.copyfile(srcfile, tmp_comp)

            tempfiles[level]['filename_comp'] = tmp_comp
            tempfiles[level]['hash_comp'] = util.hashfile(tmp_comp)
            tempfiles[level]['origsize_comp'] = os.path.getsize(tmp_comp)
            printnn('.')

    # Decompress
    if cfg.do_decompress:
        for level in cfg.levels:
            if (same_input_file):
                # Reuse compression input for this level
                tempfiles[level]['filename_decomp'] = None
                tempfiles[level]['hash_decomp'] = tempfiles[level]['hash_comp']
                tempfiles[level]['origsize_decomp'] = tempfiles[level]['origsize_comp']
            else:
                # Separate input file
                srcfile = util.findfile(cfgMultiDecomp[str(level)])

                tmp_raw = os.path.join(cfg.temp_path, f"deflatebench-decomp-{level}.tmp")
                shutil.copyfile(srcfile, tmp_raw)

                tmp_decomp = os.path.join(cfg.temp_path, f"deflatebench-decomp-{level}.gz")
                util.runcommand(f"{cfg.testtool} -{level} -c {tmp_raw}", output=tmp_decomp)

                tempfiles[level]['filename_decomp'] = tmp_decomp
                tempfiles[level]['hash_decomp'] = util.hashfile(tmp_raw)
                tempfiles[level]['origsize_decomp'] = os.path.getsize(tmp_raw)
                os.unlink(tmp_raw)

            printnn('.')
    print()

    # Print a bit of info about the selected levels and files
    print_files(cfg, tempfiles, same_input=same_input_file, level_files=True)
    print("Activated multi file mode")

    return tempfiles
