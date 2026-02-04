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

def trimworst(results):
    ''' Trim X worst results '''
    results.sort()
    if not cfgRuns['trimworst']:
        return results
    return results[:-cfgRuns['trimworst']]

def getlevels():
    levels = list(range(cfgRuns['minlevel'],cfgRuns['maxlevel']+1))
    for strategy in cfgRuns['strategies']:
        levels.append(strategy)
    return levels

def calculate(results, tempfiles):
    ''' Calculate benchmark results '''
    totsize, totsize2 = [0]*2
    totcomppct, totcomppct2 = [0]*2
    totcomptime, totcomptime2 = [0]*2
    res_comp, res_totals = dict(), dict()

    numresults = cfgRuns['runs'] - cfgRuns['trimworst']
    numlevels = len(getlevels())

    # Calculate and print stats per level
    for level in map(str, getlevels()):
        origsize = tempfiles[level]['origsize']
        comp = dict()

        # Find best/worst times for this level
        comp['compsize'] = None
        rawcomptimes = []
        for run in results[level]:
            rsize,rcompt = run
            rawcomptimes.append(rcompt)
            if comp['compsize'] is not None and comp['compsize'] != rsize:
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
    res_totals['avgpct'] = totcomppct/numlevels
    res_totals['avgtime'] = totcomptime/(numlevels*numresults)
    if cfgRuns['minlevel'] == 0:
        res_totals['avgpct2'] = totcomppct2/(numlevels-1)
        res_totals['avgtime2'] = totcomptime2/((numlevels-1)*numresults)

    return res_comp, res_totals

def printinfo():
    ''' Prints system and configuration info '''
    print("")
    util.printsysinfo()
    print("")
    print(f"Tool: {cfgRuns['testtool']} Size: {os.path.getsize(cfgRuns['testtool']):,} B")
    levelrange = f"{cfgRuns['minlevel']}-{cfgRuns['maxlevel']}"
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
    for level in map(str, getlevels()):
        compstr, decompstr = '', ''

        if do_compress:
            compstr = cli.resultstr(comp[level],28)
        if do_decompress:
            decompstr = cli.resultstr(decomp[level],30)

        print_resultline(level, comp[level]['avgpct'], compstr, decompstr, comp[level]['compsize'])

    # Print totals
    print('')
    print_resultline('avg1', comp_tot['avgpct'], f"{comp_tot['avgtime']:.4f}", f"{decomp_tot['avgtime']:.4f}")
    if cfgRuns['minlevel'] == 0:
        print_resultline('avg2', comp_tot['avgpct2'], f"{comp_tot['avgtime2']:.4f}", f"{decomp_tot['avgtime2']:.4f}")
    print('')

def benchmain():
    ''' Main benchmarking function '''
    global do_compress, do_decompress
    tempfiles = dict()

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

    # Single testfile, we just reference the same file for every level
    if cfgRuns['testmode'] == 'single':
        tmp_filename = os.path.join(cfgConfig['temp_path'], "deflatebench.tmp")
        srcfile = util.findfile(cfgSingle['testfile'])
        shutil.copyfile(srcfile,tmp_filename)
        tmp_hash = util.hashfile(tmp_filename)
        origsize = os.path.getsize(tmp_filename)
        print("Activated single file mode")
        benchmark.printfile(f"{cfgRuns['minlevel']}-{cfgRuns['maxlevel']}", srcfile)

        for level in map(str, getlevels()):
            tempfiles[level] = dict()
            tempfiles[level]['filename'] = tmp_filename
            tempfiles[level]['hash'] = tmp_hash
            tempfiles[level]['origsize'] = origsize
    else:
        # Multiple testfiles
        if cfgRuns['testmode'] == 'multi':
            print("\nActivated multiple file mode.")
        else:
            print(f"\nActivated multiple generated file mode. Source: {cfgGen['srcFile']}")

        for level in map(str, getlevels()):
            tempfiles[level] = dict()
            tmp_filename = os.path.join(cfgConfig['temp_path'], f"deflatebench-{level}.tmp")
            tempfiles[level]['filename'] = tmp_filename

            if cfgRuns['testmode'] == 'multi':
                srcfile = util.findfile(cfgMulti[level])
                shutil.copyfile(srcfile,tmp_filename)
                benchmark.printfile(f"{level}", srcfile)
            else:
                util.generate_testfile(util.findfile(cfgGen['srcFile']),tmp_filename,cfgGen[level])
                benchmark.printfile(f"{level}", tmp_filename)

            tempfiles[level]['hash'] = util.hashfile(tmp_filename)
            tempfiles[level]['origsize'] = os.path.getsize(tmp_filename)

    # Tweak system to reduce benchmark variance
    util.cputweak(True)

    # Prepare multilevel results array
    calc_comp, calc_comptot, calc_decomp, calc_decomptot = None, None, None, None
    result_comp, result_decomp = dict(), dict()
    for level in map(str, getlevels()):
        result_comp[level] = []
        result_decomp[level] = []

    # Prepare compressed files when only benchmarking decompress
    if not do_compress and cfgRuns['testmode'] != 'multi':
        printnn("Compressing tempfiles for decompression test ")
        if cfgRuns['testmode'] == 'single':
            srcfile = cfgSingle['testfile']
        else: # gen
            srcfile = cfgGen['srcFile']
        compfile = util.findfile(srcfile)

        for level in map(str, getlevels()):
            testtool = os.path.realpath(cfgRuns['testtool'])
            tmp_compfile = os.path.join(cfgConfig['temp_path'], f"{os.path.basename(srcfile)}-{level}.gz")
            util.runcommand(f"{testtool} -{level} -c {tempfiles[level]['filename']}", output=tmp_compfile)
            tempfiles[level]['filename'] = tmp_compfile
            printnn('.')
        print('')

    # Run tests and record results
    for run in range(1,cfgRuns['runs']+1):
        if run != 1:
            cfgConfig['skipverify'] = True

        print(f"Starting run {run} of {cfgRuns['runs']}")
        for level in map(str, getlevels()):
            compsize,comptime,decomptime,hashfail = benchmark.runtest(cfgRuns['testtool'], timemode, do_compress, do_decompress, cfgConfig['temp_path'],
                                                                      tempfiles, timefile, level, util.cmdprefix,
                                                                      cfgConfig['skipverify'])
            if hashfail != 0:
                print(f"ERROR: level {level} failed crc checking")
            if do_compress:
                result_comp[level].append( [compsize,comptime] )
            if do_decompress:
                result_decomp[level].append( [compsize,decomptime] )

    if do_compress:
        calc_comp,calc_comptot = calculate(result_comp, tempfiles)
    if do_decompress:
        calc_decomp,calc_decomptot = calculate(result_decomp, tempfiles)

    printinfo()
    printreport(calc_comp,calc_decomp,calc_comptot,calc_decomptot)

    # Disable system tweaks to restore normal powersaving, turbo, etc
    util.cputweak(False)

    # Clean up tempfiles
    for level in map(str, getlevels()):
        if os.path.isfile(tempfiles[level]['filename']):
            os.unlink(tempfiles[level]['filename'])

def main():
    ''' Main function handles command-line arguments and loading the correct config '''
    global cfgRuns,cfgConfig,cfgTuning,cfgGen,cfgSingle,cfgMulti

    parser = argparse.ArgumentParser(description='deflatebench - A zlib-ng benchmarking utility. Please see config file for more options.')
    parser.add_argument('-r','--runs', help='Number of benchmark runs.', type=int)
    parser.add_argument('-t','--trimworst', help='Trim the N worst runs per level.', type=int)
    parser.add_argument('-p','--profile', help='Load config profile from config file: ~/deflatebench-[PROFILE].conf')
    parser.add_argument('--write-config', help='Write default configfile to ~/deflatebench.conf.', action='store_true')
    parser.add_argument('-s','--single', help='Activate testmode "Single"', action='store_true')
    parser.add_argument('-m','--multi', help='Activate testmode "Multi".', action='store_true')
    parser.add_argument('-g','--gen', help='Activate testmode "Generate".', action='store_true')
    parser.add_argument('-l','--testtool', help='Path to test tool.', action='store')
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
