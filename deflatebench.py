#!/usr/bin/python3 -OO
import os, os.path
import sys
import re
import shlex
import shutil
import hashlib
import subprocess
from subprocess import PIPE
from datetime import datetime, date, time, timedelta

# Define some variables
runs = 15
trimcount = 5
minlevel = 1
maxlevel = 9

start_delay = 0  # Milliseconds of startup to skip measuring, requires usleep(X*1000) in minigzip main()
use_chrt = True
use_nosync = True
use_perf = True
use_turboctl = True
use_cpupower = True

skipverify = False
skipdecomp = False
skipworst = True

#testfile = "../testfil-500M"
#testfile = "../testfil-100M"
testfile = "../testfil-40M"
#testfile = "../testfil-30M"
#testfile = "../testfil-20M"

tempfile = "/tmp/runtest2.tmp"


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

def cputweak(enable):
    ''' Disable turbo, disable idlestates, and set fixed cpu mhz. Requires sudo rights. '''
    # Turn off cpu turbo and power savings
    if enable:
        if use_turboctl:
            runcommand('sudo /usr/bin/turboctl off', silent=1)
        if use_cpupower:
            runcommand('sudo /usr/bin/cpupower frequency-set -g performance -d 3600000', silent=1)
            runcommand('sudo /usr/bin/cpupower idle-set -D 2', silent=1)

    # Turn cpu turbo and power savings back on
    if not enable:
        if use_turboctl:
            runcommand('sudo /usr/bin/turboctl on')
        if use_cpupower:
            runcommand('sudo /usr/bin/cpupower frequency-set -d 1000000')
            runcommand('sudo /usr/bin/cpupower idle-set -E')

def get_len(s):
    ''' Return string length excluding ANSI escape strings '''
    return len(strip_ANSI_regex("", s))

def printnn(text):
    ''' Print without causing a newline '''
    sys.stdout.write(text)
    sys.stdout.flush()

def hashfile(file):
    ''' Calculate hash of file '''
    BUF_SIZE = 1024*1024  # lets read stuff in 1MB chunks!
    sha1 = hashlib.sha1()

    with open(file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def runcommand(command, env=None, stoponfail=1, silent=1, output='/dev/null'):
    ''' Run command, and handle special cases '''
    errout = ""
    args = shlex.split(command)
    if (silent == 1):
        devnull = open(output, 'w')
        retval = subprocess.call(args,env=env,stdout=devnull)
        devnull.close()
    else:
        retval = subprocess.call(args,env=env)
    if ((retval != 0) and (stoponfail != 0)):
        sys.exit("Failed, retval(%s): %s" % (retval, command))
    return retval

def get_env(bench=False):
    env = dict()
    if bench and use_nosync:
        env['LD_PRELOAD'] = '/usr/lib64/nosync/nosync.so'
    return env

def command_prefix(timefile):
    ''' Build the benchmarking command prefix '''
    if use_chrt:
        command = "/usr/bin/chrt -f 99"
    else:
        command = "/usr/bin/nice -n -20"

    if use_perf:
        command += " /usr/bin/perf stat -D %s -e cpu-clock:u -o '%s' -- " % (start_delay,timefile)
    else:
        timeformat="%U"
        command += " -20 /usr/bin/time -o %s -f '%s' -- " % (timefile,timeformat)

    return command

def parse_timefile(filen):
    ''' Parse output from perf or time '''
    if use_perf:
        with open(filen) as f:
            content = f.readlines()
        for line in content:
            if line[-13:-1] == 'seconds user':
                return(float(line[:-13]))
        return 0.0
    else:
        with open(filen) as f:
            content = f.readlines()
        return(float(content[0]))

def resultstr(min, avg, max):
    ''' Build result string '''
    return f"{BLUE}{min:.3f}{RESET}/{GREEN}{avg:.3f}{RESET}/{RED}{max:.3f}{RESET}"

def runtest(file,orighash,level,skipverify,skipdecomp):
    ''' Run the tests for a compression level'''
    timefile = '/tmp/zlib-time.tmp'
    compfile = '/tmp/zlib-testfil.gz'
    decompfile = '/tmp/zlib-testfil.raw'
    hashfail = 0
    decomptime = 0

    env = get_env(True)
    cmdprefix = command_prefix(timefile)

    sys.stdout.write("Testing level %s: " % (level))
    runcommand('sync')

    # Compress
    printnn('c')
    runcommand("%s ./minigzip -%s -c %s" % (cmdprefix,level,file), env=env, output=compfile)
    compsize = os.path.getsize(compfile)

    comptime = parse_timefile(timefile)

    # Decompress
    if not skipdecomp or not skipverify:
        printnn('d')
        runcommand("%s ./minigzip -d -c %s" % (cmdprefix,compfile), env=env, output=decompfile)

        decomptime = parse_timefile(timefile)

        if not skipverify:
            ourhash = hashfile(decompfile)
            if ourhash != orighash:
                print("%s != %s" % (orighash,ourhash))
                hashfail = 1

        os.unlink(decompfile)

    # Validate using gunzip
    if not skipverify:
        printnn('v')
        runcommand("gunzip -k -c %s" % (compfile), output=decompfile)

        gziphash = hashfile(decompfile)
        if gziphash != orighash:
            print("%s != %s" % (orighash,gziphash))
            hashfail = 1

        os.unlink(decompfile)

    os.unlink(timefile)
    os.unlink(compfile)

    printnn(" %.3f %.3f" % (comptime, decomptime))
    printnn('\n')

    return compsize,comptime,decomptime,hashfail

def trimworst(results):
    ''' Trim X worst results '''
    results.sort()
    return results[:-trimcount]

def printreport(results, origsize):
    ''' Print results table '''
    totsize = 0
    totcomptime = 0
    totdecomptime = 0
    totsize2 = 0
    totcomptime2 = 0
    totdecomptime2 = 0
    numresults = runs - trimcount

    numlevels = len(range(minlevel,maxlevel+1))

    print("\n Runs: %s" % (runs))
    print(" Levels: %s-%s" % (minlevel, maxlevel))
    print(" Skipworst: %s (%s)" % (skipworst, trimcount))

    if skipdecomp:
        print("\n Level   Comp   Comptime min/avg/max")
    else:
        print("\n Level   Comp   Comptime min/avg/max  Decomptime min/avg/max")

    for i in range(0,numlevels):
        ltotcomptime, ltotdecomptime = [0,0]

        # Find best/worst times for level
        compsize = None
        rawcomptimes = []
        rawdecomptimes = []
        for run in results:
            rlevel,rsize,rcompt,rdecompt = run[i]
            rawcomptimes.append(rcompt)
            rawdecomptimes.append(rdecompt)
            if not compsize is None and compsize != rsize:
                print("Warning: size changed between runs. Expected: %s Got: %s" % (compsize, rsize))
            else:
                compsize = rsize

        # Trim the worst results
        comptimes = trimworst(rawcomptimes)
        decomptimes = trimworst(rawdecomptimes)

        # Calculate min/max and sum per level
        mincomptime = min(comptimes)
        mindecomptime = min(decomptimes)

        maxcomptime = max(comptimes)
        maxdecomptime = max(decomptimes)

        ltotcomptime += sum(comptimes)
        ltotdecomptime += sum(decomptimes)

        # Store values for grand total
        totsize += rsize
        totcomptime += ltotcomptime
        totdecomptime += ltotdecomptime
        if i != 0:
            totsize2 += rsize
            totcomptime2 += ltotcomptime
            totdecomptime2 += ltotdecomptime

        # Compute and print values for this level
        comp = float(rsize*100)/origsize
        avgcomptime = ltotcomptime/numresults
        avgdecomptime = ltotdecomptime/numresults

        # Print level results
        compstr = resultstr(mincomptime, avgcomptime, maxcomptime)
        if skipdecomp:
            decompstr = ""
        else:
            decompstr = resultstr(mindecomptime, avgdecomptime, maxdecomptime)
        compstrpad = ' ' * (20 - get_len(compstr))
        decompstrpad = ' ' * (23 - get_len(decompstr))

        print(" %-5s %7.3f%% %s%s %s%s  %s " % (rlevel,comp,compstrpad,compstr,decompstrpad,decompstr,compsize))

    ### Totals
    # Compression times
    avgcomp = (float(totsize/numlevels)*100)/origsize
    avgcomp2 = (float(totsize2/(numlevels-1))*100)/origsize
    avgcomptime = totcomptime/(numlevels*numresults)
    avgcomptime2 = totcomptime2/((numlevels-1)*numresults)

    # Decompression times
    if skipdecomp:
        avgdecomptime, avgdecompstr, totdecompstr = [''] * 3
        avgdecomptime2, avgdecompstr2, totdecompstr2 = [''] * 3
    else:
        avgdecomptime = totdecomptime/(numlevels*numresults)
        avgdecompstr = "%.3f" % (avgdecomptime)
        totdecompstr = "%.3f" % (totdecomptime)
        if minlevel == 0:
            avgdecomptime2 = totdecomptime2/((numlevels-1)*numresults)
            avgdecompstr2 = "%.3f" % (avgdecomptime2)
            totdecompstr2 = "%.3f" % (totdecomptime2)

    print("\n %-5s %7.3f%% %20.3f %23s" % ('avg1',avgcomp,avgcomptime,avgdecompstr))
    if minlevel == 0:
        print(" %-5s %7.3f%% %20.3f %23s  (lvl 0 excluded)" % ('avg2',avgcomp2,avgcomptime2,avgdecompstr2))
    print(" %-5s %8s %20.3f %23s" % ('tot','',totcomptime,totdecompstr))


def main():
    global skipworst, skipverify, runs, trimcount
    shutil.copyfile(testfile,tempfile)
    hash = hashfile(tempfile)
    origsize = os.path.getsize(tempfile)

    if len(sys.argv) >= 2:
        runs = int(sys.argv[1])

    if len(sys.argv) == 3:
        trimcount = int(sys.argv[2])
        skipworst = True

    if skipworst and runs <= trimcount:
        timcount = runs - 1

    cputweak(True)

    # Run tests and record results
    results = []
    for run in range(1,runs+1):
        if run != 1:
            skipverify = True

        temp = []
        print("Starting run %s of %s" % (run,runs))
        for level in range(minlevel,maxlevel+1):
            compsize,comptime,decomptime,hashfail = runtest(tempfile,hash,level,skipverify,skipdecomp)
            if hashfail != 0:
                print("ERROR: level %s failed crc checking" % (level))
            temp.append( [level,compsize,comptime,decomptime] )
        results.append(temp)

    printreport(results, origsize)

    cputweak(False)

    os.unlink(tempfile)


main()
