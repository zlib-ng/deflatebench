#!/usr/bin/python3 -OOB
""" deflatebench.py -- A util that benchmarks minigzip/minideflate.

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import os, os.path
import sys
import shutil
import argparse
import statistics

from includes import benchmark
from includes import cli
from includes import config
from includes import util

from includes.cli import printnn

levels = None

def trimworst(results):
    ''' Trim X worst results '''
    results.sort()
    if not cfgRuns['trimworst']:
        return results
    return results[:-cfgRuns['trimworst']]

def calculate(results, tempfiles, is_compress):
    ''' Calculate benchmark results '''
    totsize, totsize2 = [0]*2
    totcomppct, totcomppct2 = [0]*2
    totcomptime, totcomptime2 = [0]*2
    res_comp, res_totals = dict(), dict()

    numresults = cfgRuns['runs'] - cfgRuns['trimworst']
    numlevels = len(levels)

    # Calculate and print stats per level
    for level in levels:
        if is_compress:
            origsize = tempfiles[level]['origsize_comp']
        else:
            origsize = tempfiles[level]['origsize_decomp']
        comp = dict()

        # Find best/worst times for this level
        comp['compsize'] = None
        rawcomptimes = []
        for run in results[level]:
            rsize,rcompt = run
            rawcomptimes.append(rcompt)
            if is_compress and comp['compsize'] is not None and comp['compsize'] != rsize:
                print(f"Warning: size changed between runs. Expected: {comp['compsize']} Got: {rsize}")
            else:
                comp['compsize'] = rsize

        # Trim the worst results
        comptimes = trimworst(rawcomptimes)

        # Compute averages
        comp['avgtime'] = statistics.mean(comptimes)
        comp['avgpct'] = float(rsize*100)/origsize

        # Compute stddev
        if numresults >= 2:
            comp['stddev'] = statistics.stdev(comptimes, comp['avgtime'])
        else:
            comp['stddev'] = 0

        # Calculate min/max and sum for this level
        comp['mintime']   = min(comptimes)
        comp['maxtime']   = max(comptimes)

        # Store values for grand total
        tmp_comptime = sum(comptimes)

        totsize += rsize
        totcomppct += comp['avgpct']
        totcomptime += tmp_comptime
        if level != 0:
            totsize2 += rsize
            totcomppct2 += comp['avgpct']
            totcomptime2 += tmp_comptime

        # Put this levels results into the aggregate
        res_comp[level] = dict(comp.items())

    ### Totals
    res_totals['numresults'] = numresults
    res_totals['numlevels'] = numlevels
    res_totals['totsize'] = totsize

    # Averages/Totals
    res_totals['tottime'] = totcomptime
    if numlevels > 1:
        res_totals['avgpct'] = totcomppct/numlevels
        res_totals['avgtime'] = totcomptime/(numlevels*numresults)
        if 0 in levels:
            res_totals['avgpct2'] = totcomppct2/(numlevels-1)
            res_totals['avgtime2'] = totcomptime2/((numlevels-1)*numresults)

    return res_comp, res_totals

def printinfo():
    ''' Prints system and configuration info '''
    print("")
    util.printsysinfo()
    print("")
    print(f"Tool: {cfgRuns['testtool']} Size: {os.path.getsize(cfgRuns['testtool']):,} B")
    levelrange = ','.join(map(str, levels))
    print(f"Levels: {levelrange:10}")
    print(f"Runs: {str(cfgRuns['runs']):10} Trim worst: {str(cfgRuns['trimworst']):10}")
    print("")

def print_resultline(header,pct,comp,decomp,size=None):
    printnn(f" {header:5}")
    if isinstance(pct, float):
        printnn(f"{pct:>7.3f}% ")
    else:
        printnn(f"{pct:>8} ")
    if do_compress:
        printnn(f"{comp:>28} ")
    if do_decompress:
        printnn(f"{decomp:>30} ")
    if size is not None:
        printnn(f" {size:15}")
    print('')

def printreport(comp,decomp,comp_tot,decomp_tot):
    ''' Print results table '''
    # Little hack to provide results that we can then ignore, simplifies the code
    if not do_compress:
        comp = decomp
        comp_tot = decomp_tot
    elif not do_decompress:
        decomp = comp
        decomp_tot = comp_tot

    # Print header
    print_resultline('Level', 'Comp', 'Comptime min/avg/max/stddev', 'Decomptime min/avg/max/stddev', 'Compressed size')

    # Print level results
    for level in levels:
        compstr, decompstr = '', ''

        if do_compress:
            compstr = cli.resultstr(comp[level],28)
        if do_decompress:
            decompstr = cli.resultstr(decomp[level],30)

        print_resultline(level, comp[level]['avgpct'], compstr, decompstr, comp[level]['compsize'])

    # Print totals
    print('')
    if len(levels) > 1:
        print_resultline('avg1', comp_tot['avgpct'], f"{comp_tot['avgtime']:.4f}", f"{decomp_tot['avgtime']:.4f}")
        if 0 in levels:
            print_resultline('avg2', comp_tot['avgpct2'], f"{comp_tot['avgtime2']:.4f}", f"{decomp_tot['avgtime2']:.4f}")
        print('')

def benchmain():
    ''' Main benchmarking function '''
    global do_compress, do_decompress, levels
    tempfiles = dict()
    separate_files = False

    levels = benchmark.parse_levels(cfgRuns['levels'])
    timefile = os.path.join(cfgConfig['temp_path'], 'zlib-time.tmp')

    if cfgConfig['benchmark'] == 'compress':
        do_compress = True
        do_decompress = False
    elif cfgConfig['benchmark'] == 'decompress':
        do_compress = False
        do_decompress = True
    else:
        do_compress = True
        do_decompress = True

    # Detect external tools
    timemode = util.find_tools(timefile, use_prio=cfgTuning['use_prio'], use_perf=cfgConfig['use_perf'],
                                use_turboctl=cfgTuning['use_turboctl'], use_cpupower=cfgTuning['use_cpupower'])

    printinfo()

    for level in levels:
        tempfiles[level] = dict()

    # Single mode, we just reference the same file for every level
    if cfgRuns['testmode'] == 'single':
        # filename_comp
        if do_compress:
            tmp_compress_in = os.path.join(cfgConfig['temp_path'], "deflatebench-comp.tmp")
            srcfile_comp = util.findfile(cfgSingle['testfile_compress'])
            shutil.copyfile(srcfile_comp,tmp_compress_in)
            compress_hash = util.hashfile(tmp_compress_in)
            compress_origsize = os.path.getsize(tmp_compress_in)
        else:
            tmp_compress_in = None
            compress_hash = None
            compress_origsize = None

        # filename_decomp
        if do_decompress:
            tmp_decompress_in = os.path.join(cfgConfig['temp_path'], "deflatebench-decomp.tmp")
            srcfile_decomp = util.findfile(cfgSingle['testfile_decompress'])
            if do_compress and cfgSingle['testfile_compress'] == cfgSingle['testfile_decompress']:
                tmp_decompress_in = None
                decompress_hash = compress_hash
                decompress_origsize = compress_origsize
            else: # Use separate files for compress and decompress benchmarks
                #shutil.copyfile(srcfile,tmp_decompress_in)
                separate_files = True
                decompress_hash = util.hashfile(srcfile_decomp)
                decompress_origsize = os.path.getsize(srcfile_decomp)

                # Prepare compressed files when only benchmarking decompress
                printnn("Compressing tempfiles for decompression test ")
                testtool = os.path.realpath(cfgRuns['testtool'])
                for level in map(str, levels):
                    tmp_decompress_in = os.path.join(cfgConfig['temp_path'], f"{os.path.basename(srcfile_decomp)}-{level}.gz")
                    util.runcommand(f"{testtool} -{level} -c {srcfile_decomp}", output=tmp_decompress_in)
                    tempfiles[level]['filename_decomp'] = tmp_decompress_in
                    printnn('.')
        else:
            tmp_decompress_in = None
            decompress_hash = None
            decompress_origsize = None

        print("Activated single file mode")
        if separate_files:
            if do_compress:
                benchmark.printfile(','.join(map(str, levels)), srcfile_comp, 'Compression')
            if do_decompress:
                benchmark.printfile(','.join(map(str, levels)), srcfile_decomp, 'Decompression')
        else:
            benchmark.printfile(','.join(map(str, levels)), srcfile_comp)


        for level in levels:
            tempfiles[level]['filename_comp'] = tmp_compress_in
            if not separate_files:
                tempfiles[level]['filename_decomp'] = tmp_decompress_in
            tempfiles[level]['hash_comp'] = compress_hash
            tempfiles[level]['hash_decomp'] = decompress_hash
            tempfiles[level]['origsize_comp'] = compress_origsize
            tempfiles[level]['origsize_decomp'] = decompress_origsize
    else:
        # Multiple testfiles
        if cfgRuns['testmode'] == 'multi':
            print("\nActivated multiple file mode.")
        else:
            print(f"\nActivated multiple generated file mode. Source: {cfgGen['srcFile']}")

        for level in levels:
            tmp_filename = os.path.join(cfgConfig['temp_path'], f"deflatebench-{level}.tmp")
            tempfiles[level]['filename_comp'] = tmp_filename
            tempfiles[level]['filename_decomp'] = None

            if cfgRuns['testmode'] == 'multi':
                srcfile = util.findfile(cfgMulti[str(level)])
                shutil.copyfile(srcfile,tmp_filename)
                benchmark.printfile(f"{level}", srcfile)
            else:
                util.generate_testfile(util.findfile(cfgGen['srcFile']),tmp_filename,cfgGen[str(level)])
                benchmark.printfile(f"{level}", tmp_filename)

            tempfiles[level]['hash'] = util.hashfile(tmp_filename)
            tempfiles[level]['origsize_comp'] = os.path.getsize(tmp_filename)

    # Tweak system to reduce benchmark variance
    util.cputweak(True)

    # Prepare testconfig dict
    testconfig = dict()
    testconfig['runs'] = cfgRuns['runs']
    testconfig['levels'] = levels
    testconfig['skipverify'] = cfgConfig['skipverify']
    testconfig['timemode'] = timemode
    testconfig['timefile'] = timefile
    testconfig['cmdprefix'] = util.cmdprefix
    testconfig['testtool'] = os.path.realpath(cfgRuns['testtool'])
    testconfig['do_compress'] = do_compress
    testconfig['do_decompress'] = do_decompress
    testconfig['tempfiles'] = tempfiles
    testconfig['temp_path'] = cfgConfig['temp_path']

    # Run tests and record results
    result_comp,result_decomp = benchmark.run_tests(testconfig)

    # Calculate statistics
    calc_comp, calc_comptot, calc_decomp, calc_decomptot = None, None, None, None

    if do_compress:
        calc_comp,calc_comptot = calculate(result_comp, tempfiles, True)
    if do_decompress:
        calc_decomp,calc_decomptot = calculate(result_decomp, tempfiles, False)

    # Print info and results
    printinfo()
    printreport(calc_comp,calc_decomp,calc_comptot,calc_decomptot)

    # Disable system tweaks to restore normal powersaving, turbo, etc
    util.cputweak(False)

    # Clean up tempfiles
    for level in levels:
        filename_comp = tempfiles[level]['filename_comp']
        if do_compress and os.path.isfile(filename_comp):
            os.unlink(filename_comp)
        filename_decomp = tempfiles[level]['filename_decomp']
        if do_decompress and filename_decomp and os.path.isfile(filename_decomp):
            os.unlink(filename_decomp)

def main():
    ''' Main function handles command-line arguments and loading the correct config '''
    global cfgRuns,cfgConfig,cfgTuning,cfgGen,cfgSingle,cfgMulti

    parser = argparse.ArgumentParser(description='deflatebench - A zlib-ng benchmarking utility. Please see config file for more options.')
    parser.add_argument('-p','--profile', help='Load config profile from config file: ~/deflatebench-[PROFILE].conf')
    parser.add_argument('--write-config', help='Write default configfile to ~/deflatebench.conf.', action='store_true')
    parser.add_argument('-l','--levels', help='Comma separated list of levels or level ranges.', action='store')
    parser.add_argument('-r','--runs', help='Number of benchmark runs.', type=int)
    parser.add_argument('--trimworst', help='Trim the N worst runs per level.', type=int)
    parser.add_argument('-s','--single', help='Activate testmode "Single"', action='store_true')
    parser.add_argument('-m','--multi', help='Activate testmode "Multi".', action='store_true')
    parser.add_argument('-g','--gen', help='Activate testmode "Generate".', action='store_true')
    parser.add_argument('-f','--file', help='Path to test file to use for both comp/decomp (Single/Gen mode only).', action='store')
    parser.add_argument('-x','--file-compress', help='Path to test file to use for compress (Single mode only).', action='store', dest='file_comp')
    parser.add_argument('-y','--file-decompress', help='Path to test file to use for decompress (Single mode only).', action='store', dest='file_decomp')
    parser.add_argument('--testtool', help='Path to test tool.', action='store')
    parser.add_argument('--benchmark', choices=['both','compress','decompress'], help='By default, benchmark both compress and decompress.', action='store')
    parser.add_argument('--skipverify', help='Skip verifying compressed files with system gzip.', action='store_true')
    args = parser.parse_args()

    defconfig_path = util.findfile('deflatebench.conf',fatal=False)

    # Write default config file
    if args.write_config:
        if not defconfig_path:
            defconfig_path = os.path.join( os.path.expanduser("~"), 'deflatebench.conf')
            config.writeconfig(defconfig_path)
        else:
            print(f"ERROR: {defconfig_path} already exists, not overwriting.")
        sys.exit(1)

    # Load defconfig, then potentially override with values from config file
    cfg = config.defconfig()
    if args.profile and not args.profile == 'default':
        profilename = f"deflatebench-{args.profile}.conf"
        profilefile = util.findfile(profilename, fatal=True)
        cfgtmp = config.parseconfig(profilefile)
        cfg = config.mergeconfig(cfg,cfgtmp)
        print(f"Loaded config file '{profilefile}'.")
    elif defconfig_path:
        cfgtmp = config.parseconfig(defconfig_path)
        cfg = config.mergeconfig(cfg,cfgtmp)
        print(f"Loaded config file '{defconfig_path}'.")
    else:
        print("Loaded default config.")

    # Split config into separate dicts
    cfgRuns = cfg['Testruns']
    cfgConfig = cfg['Config']
    cfgTuning = cfg['Tuning']
    cfgGen = cfg['Testdata_Gen']
    cfgSingle = cfg['Testdata_Single']
    cfgMulti = cfg['Testdata_Multi']

    util.init(cfgConfig, cfgTuning)

    # Handle commandline parameters
    if args.runs is not None:
        cfgRuns['runs'] = args.runs

    if args.trimworst is not None:
        cfgRuns['trimworst'] = args.trimworst

    if cfgRuns['runs'] <= cfgRuns['trimworst']:
        print(f"Error, parameter 'runs={cfgRuns['runs']}' needs to be higher than parameter 'trimworst={cfgRuns['trimworst']}'")
        sys.exit(1)

    if args.levels:
        cfgRuns['levels'] = args.levels

    if args.single:
        cfgRuns['testmode'] = 'single'
        if args.multi or args.gen:
            print("Error, parameter '--single' conflicts with parameters '--multi' and '--gen'")
            sys.exit(1)

    if args.multi:
        cfgRuns['testmode'] = 'multi'
        if args.single or args.gen:
            print("Error, parameter '--multi' conflicts with parameters '--single' and '--gen'")
            sys.exit(1)

    if args.gen:
        cfgRuns['testmode'] = 'gen'
        if args.single or args.multi:
            print("Error, parameter '--gen' conflicts with parameters '--single' and '--multi'")
            sys.exit(1)

    # Handle testfile error cases
    if args.file and (args.file_comp or args.file_decomp):
        print("Error, parameter '--file' conflicts with parameters '--file-compress' and '--file-decompress'")
        sys.exit(1)
    elif (args.file_comp or args.file_decomp) and cfgRuns['testmode'] != 'single':
        print("Error, parameters '--file-compress' and '--file-decompress' are only available with '--single'")
        sys.exit(1)
    elif args.file and cfgRuns['testmode'] == 'multi':
        print("Error, parameter '--file' is not compatible with '--multi', please use config file.")
        sys.exit(1)

    # Handle testfile selection
    if args.file:
        cfgSingle['testfile_compress'] = args.file
        cfgSingle['testfile_decompress'] = args.file
        cfgGen['srcFile'] = args.file

    if args.file_comp:
        cfgSingle['testfile_compress'] = args.file_comp

    if args.file_decomp:
        cfgSingle['testfile_decompress'] = args.file_decomp

    if args.testtool:
        cfgRuns['testtool'] = args.testtool

    if 'minigzip' not in cfgRuns['testtool'] and 'minideflate' not in cfgRuns['testtool']:
        print("Error, config file spesifies invalid testtool. Valid choices are 'minigzip' and 'minideflate'.")
        sys.exit(1)

    if not os.path.isfile( os.path.join( os.getcwd(), cfgRuns['testtool']) ):
        print(f"Error, unable to find '{cfgRuns['testtool']}' in current directory, did you forget to compile?")
        sys.exit(1)

    if args.benchmark == 'decompress':
        cfgConfig['benchmark'] = 'decompress'
    elif args.benchmark == 'compress':
        cfgConfig['benchmark'] = 'compress'

    if args.skipverify:
        cfgConfig['skipverify'] = True

    # Run main benchmarking function
    benchmain()
main()
