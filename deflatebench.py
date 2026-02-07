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

def print_resultline(header,comp_pct,comp_size,comp,decomp_pct,decomp_size,decomp):
    printnn(f" {header:5}")
    if do_compress:
        if isinstance(comp_pct, float):
            printnn(f"{comp_pct:>7.3f}% ")
        else:
            printnn(f"{comp_pct:>8} ")
        printnn(f"{comp_size:>12} ")
        printnn(f"{comp:>28}")
    if do_compress and do_decompress:
        printnn('  ')
    if do_decompress:
        if isinstance(decomp_pct, float):
            printnn(f"{decomp_pct:>7.3f}% ")
        else:
            printnn(f"{decomp_pct:>8} ")
        printnn(f"{decomp_size:>12} ")
        printnn(f"{decomp:>30}")
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
    if do_compress and do_decompress:
        print_resultline('', '|-     ', 'Compress', '-|', '|-     ', 'Decompress', '-|')
    print_resultline('Level', 'Comp %', 'Out size', 'Comptime min/avg/max/stddev', 'Comp %', 'In size', 'Decomptime min/avg/max/stddev')

    # Print level results
    for level in levels:
        compstr, decompstr = '', ''

        if do_compress:
            compstr = cli.resultstr(comp[level],28)
        if do_decompress:
            decompstr = cli.resultstr(decomp[level],30)

        print_resultline(level, comp[level]['avgpct'], comp[level]['compsize'], compstr, decomp[level]['avgpct'], decomp[level]['compsize'], decompstr)

    # Print totals
    print('')
    if len(levels) > 1:
        print_resultline('avg1', comp_tot['avgpct'], '', f"{comp_tot['avgtime']:.4f}", decomp_tot['avgpct'], '', f"{decomp_tot['avgtime']:.4f}")
        if 0 in levels:
            print_resultline('avg2', comp_tot['avgpct2'], '', f"{comp_tot['avgtime2']:.4f}", decomp_tot['avgpct2'], '', f"{decomp_tot['avgtime2']:.4f}")
        print('')

def benchmain():
    ''' Main benchmarking function '''
    global do_compress, do_decompress, levels
    tempfiles = dict()

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
    testconfig['temp_path'] = cfgConfig['temp_path']

    # Prepare tempfiles according to testmode selection
    if cfgRuns['testmode'] == 'single':
        tempfiles = benchmark.prepare_singlemode(testconfig, cfgSingle)
    elif cfgRuns['testmode'] == 'gen':
        tempfiles = benchmark.prepare_genmode(testconfig, cfgGenComp, cfgGenDecomp)
    elif cfgRuns['testmode'] == 'multi':
        tempfiles = benchmark.prepare_multimode(testconfig, cfgMultiComp, cfgMultiDecomp)
    testconfig['tempfiles'] = tempfiles

    # Tweak system to reduce benchmark variance
    util.cputweak(True)

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
    global cfgRuns,cfgConfig,cfgTuning,cfgSingle,cfgGenComp,cfgGenDecomp,cfgMultiComp,cfgMultiDecomp

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
    parser.add_argument('-x','--file-compress', help='Path to test file to use for compress (Single/Gen mode only).', action='store', dest='file_comp')
    parser.add_argument('-y','--file-decompress', help='Path to test file to use for decompress (Single/Gen mode only).', action='store', dest='file_decomp')
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
    cfgSingle = cfg['Testdata_Single']
    cfgGenComp = cfg['Testdata_Gen_Comp']
    cfgGenDecomp = cfg['Testdata_Gen_Decomp']
    cfgMultiComp = cfg['Testdata_Multi_Comp']
    cfgMultiDecomp = cfg['Testdata_Multi_Decomp']

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
    elif (args.file or args.file_comp or args.file_decomp) and cfgRuns['testmode'] == 'multi':
        print("Error, parameters '--file', '--file-compress' and '--file-decompress' are not compatible with '--multi', please use config file.")
        sys.exit(1)

    # Handle testfile selection
    if args.file:
        cfgSingle['testfile_compress'] = args.file
        cfgSingle['testfile_decompress'] = args.file
        cfgGenComp['srcFile'] = args.file
        cfgGenDecomp['srcFile'] = args.file

    if args.file_comp:
        cfgSingle['testfile_compress'] = args.file_comp
        cfgGenComp['srcFile'] = args.file_comp

    if args.file_decomp:
        cfgSingle['testfile_decompress'] = args.file_decomp
        cfgGenDecomp['srcFile'] = args.file_decomp

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
