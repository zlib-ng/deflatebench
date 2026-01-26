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
    totdecomptime, totdecomptime2 = [0]*2
    res_comp, res_decomp, res_totals = dict(), dict(), dict()

    numresults = cfgRuns['runs'] - cfgRuns['trimworst']
    numlevels = len(getlevels())

    # Calculate and print stats per level
    for level in map(str, getlevels()):
        origsize = tempfiles[level]['origsize']
        comp, decomp = dict(), dict()

        # Find best/worst times for this level
        comp['compsize'] = None
        rawcomptimes = []
        rawdecomptimes = []
        for run in results[level]:
            rsize,rcompt,rdecompt = run
            rawcomptimes.append(rcompt)
            rawdecomptimes.append(rdecompt)
            if comp['compsize'] is not None and comp['compsize'] != rsize:
                print(f"Warning: size changed between runs. Expected: {comp['compsize']} Got: {rsize}")
            else:
                comp['compsize'] = rsize

        # Trim the worst results
        comptimes = trimworst(rawcomptimes)
        decomptimes = trimworst(rawdecomptimes)

        # Compute averages
        comp['avgtime']   = statistics.mean(comptimes)
        decomp['avgtime'] = statistics.mean(decomptimes)
        comp['avgpct'] = float(rsize*100)/origsize

        # Compute stddev
        if numresults >= 2:
            comp['stddev']   = statistics.stdev(comptimes, comp['avgtime'])
            decomp['stddev'] = statistics.stdev(decomptimes, decomp['avgtime'])
        else:
            comp['stddev']   = 0
            decomp['stddev'] = 0

        # Calculate min/max and sum for this level
        comp['mintime']   = min(comptimes)
        comp['maxtime']   = max(comptimes)
        decomp['mintime'] = min(decomptimes)
        decomp['maxtime'] = max(decomptimes)

        # Store values for grand total
        tmp_comptime = sum(comptimes)
        tmp_decomptime = sum(decomptimes)

        totsize += rsize
        totcomppct += comp['avgpct']
        totcomptime += tmp_comptime
        totdecomptime += tmp_decomptime
        if level != 0:
            totsize2 += rsize
            totcomppct2 += comp['avgpct']
            totcomptime2 += tmp_comptime
            totdecomptime2 += tmp_decomptime

        # Put this levels results into the aggregate
        res_comp[level] = dict(comp.items())
        res_decomp[level] = dict(decomp.items())

    ### Totals
    res_totals['numresults'] = numresults
    res_totals['numlevels'] = numlevels
    res_totals['totsize'] = totsize

    # Compression
    res_totals['totcomptime'] = totcomptime
    res_totals['avgcomppct'] = totcomppct/numlevels
    res_totals['avgcomptime'] = totcomptime/(numlevels*numresults)
    if cfgRuns['minlevel'] == 0:
        res_totals['avgcomppct2'] = totcomppct2/(numlevels-1)
        res_totals['avgcomptime2'] = totcomptime2/((numlevels-1)*numresults)

    # Decompression
    if cfgConfig['skipdecomp']:
        res_totals['totdecomptime'] = totdecomptime
        res_totals['avgdecomptime'], res_totals['avgdecompstr'], res_totals['totdecompstr'] = [''] * 3
        res_totals['avgdecomptime2'], res_totals['avgdecompstr2'], res_totals['totdecompstr2'] = [''] * 3
    else:
        res_totals['avgdecomptime'] = totdecomptime/(res_totals['numlevels'] * res_totals['numresults'])
        res_totals['avgdecompstr'] = f"{res_totals['avgdecomptime']:.4f}"
        res_totals['totdecompstr'] = f"{totdecomptime:.4f}"
        if cfgRuns['minlevel'] == 0:
            res_totals['avgdecomptime2'] = totdecomptime2/((res_totals['numlevels'] - 1) * res_totals['numresults'])
            res_totals['avgdecompstr2'] = f"{res_totals['avgdecomptime2']:.4f}"
            res_totals['totdecompstr2'] = f"{totdecomptime2:.4f}"

    return res_comp, res_decomp, res_totals

def printreport(comp,decomp,totals):
    ''' Print results table '''
    # Print config info

    print("\n")
    util.printsysinfo()
    print(f"Tool: {cfgRuns['testtool']} Size: {os.path.getsize(cfgRuns['testtool']):,} B")
    levelrange = f"{cfgRuns['minlevel']}-{cfgRuns['maxlevel']}"
    print(f"Levels: {levelrange:10}")
    print(f"Runs: {str(cfgRuns['runs']):10} Trim worst: {str(cfgRuns['trimworst']):10}")

    # Print header
    if cfgConfig['skipdecomp']:
        print("\n Level   Comp   Comptime min/avg/max/stddev   Compressed size")
    else:
        print("\n Level   Comp   Comptime min/avg/max/stddev  Decomptime min/avg/max/stddev  Compressed size")

    for level in map(str, getlevels()):
        # Print level results
        compstr = cli.resultstr(comp[level],28)
        decompstr = ""
        if not cfgConfig['skipdecomp']:
            decompstr = cli.resultstr(decomp[level],30)

        print(f" {level:5}{comp[level]['avgpct']:7.3f}% {compstr} {decompstr}  {comp[level]['compsize']:15,}")

    # Print totals
    print(f"\n {'avg1':5}{totals['avgcomppct']:7.3f}% {totals['avgcomptime']:28.4f} {totals['avgdecompstr']:>30}")
    if cfgRuns['minlevel'] == 0:
        print(f" {'avg2':5}{totals['avgcomppct2']:7.3f}% {totals['avgcomptime2']:28.4f} {totals['avgdecompstr2']:>30}")

    if cfgConfig['skipdecomp']:
        print(f" {'tot':5} {'':8}{totals['totcomptime']:28.4f}   {totals['totsize']:15,}")
    else:
        print(f" {'tot':5} {'':8}{totals['totcomptime']:28.4f} {totals['totdecompstr']:>30}  {totals['totsize']:15,}")

def printfile(level,filename):
    ''' Prints formatted information about file '''
    filesize = os.path.getsize(filename)
    print(f"Level {level}: {filename} {filesize/1024/1024:6.1f} MiB  {filesize:12,} B")

def benchmain():
    ''' Main benchmarking function '''
    tempfiles = dict()

    timefile = os.path.join(cfgConfig['temp_path'], 'zlib-time.tmp')

    # Detect external tools
    benchmode = util.find_tools(timefile, use_prio=cfgTuning['use_prio'], use_perf=cfgConfig['use_perf'],
                                use_turboctl=cfgTuning['use_turboctl'], use_cpupower=cfgTuning['use_cpupower'])

    util.printsysinfo()
    print(f"Tool: {cfgRuns['testtool']} Size: {os.path.getsize(cfgRuns['testtool']):,} B")
    print(f"Timings mode: {benchmode}")

    # Single testfile, we just reference the same file for every level
    if cfgRuns['testmode'] == 'single':
        tmp_filename = os.path.join(cfgConfig['temp_path'], "deflatebench.tmp")
        srcfile = util.findfile(cfgSingle['testfile'])
        shutil.copyfile(srcfile,tmp_filename)
        tmp_hash = util.hashfile(tmp_filename)
        origsize = os.path.getsize(tmp_filename)
        print("\nActivated single file mode")
        printfile(f"{cfgRuns['minlevel']}-{cfgRuns['maxlevel']}", srcfile)

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
                printfile(f"{level}", srcfile)
            else:
                util.generate_testfile(util.findfile(cfgGen['srcFile']),tmp_filename,cfgGen[level])
                printfile(f"{level}", tmp_filename)

            tempfiles[level]['hash'] = util.hashfile(tmp_filename)
            tempfiles[level]['origsize'] = os.path.getsize(tmp_filename)

    # Tweak system to reduce benchmark variance
    util.cputweak(True)

    # Prepare multilevel results array
    results = dict()
    for level in map(str, getlevels()):
        results[level] = []

    # Run tests and record results
    for run in range(1,cfgRuns['runs']+1):
        if run != 1:
            cfgConfig['skipverify'] = True

        print(f"Starting run {run} of {cfgRuns['runs']}")
        for level in map(str, getlevels()):
            compsize,comptime,decomptime,hashfail = benchmark.runtest(cfgRuns['testtool'], benchmode, cfgConfig['temp_path'],
                                                                      tempfiles, timefile, level, util.cmdprefix,
                                                                      cfgConfig['skipdecomp'], cfgConfig['skipverify'])
            if hashfail != 0:
                print(f"ERROR: level {level} failed crc checking")
            results[level].append( [compsize,comptime,decomptime] )

    res_comp,res_decomp,res_totals = calculate(results, tempfiles)
    printreport(res_comp,res_decomp,res_totals)

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
    parser.add_argument('--skipdecomp', help='Skip decompression benchmarks.', action='store_true')
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

    if args.skipdecomp:
        cfgConfig['skipdecomp'] = True

    if args.skipverify:
        cfgConfig['skipverify'] = True

    # Run main benchmarking function
    benchmain()
main()
