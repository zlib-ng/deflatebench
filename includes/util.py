""" util.py -- Selfcontained helperfunctions.

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""

import os, os.path
import sys
import hashlib
import math
import platform
import subprocess
import shlex
import shutil

BUF_SIZE = 1024*1024  # lets read stuff in 1MB chunks when hashing or copying
cmdprefix = ''

def init(inConfig, inTuning):
    ''' Initialize variables '''
    global cfgConfig, cfgTuning
    cfgConfig = inConfig
    cfgTuning = inTuning

def get_env(bench=False):
    ''' Build dict of environment variables '''
    env = dict()
    return env

def printsysinfo():
    ''' Print system information '''
    uname = platform.uname()
    print(f"\nOS: {uname.system} {uname.release} {uname.version} {uname.machine}")
    print(f"CPU: {platform.processor()}")

def find_tools(timefile, use_prio=True, use_perf=True, use_turboctl=True, use_cpupower=False):
    global cmdprefix, chrt_exe, nice_exe, perf_exe, time_exe, turboctl_exe, cpupower_exe
    time_exe = shutil.which('time')
    perf_exe = shutil.which('perf')
    turboctl_exe = shutil.which('turboctl')
    cpupower_exe = shutil.which('cpupower')

    if use_turboctl and turboctl_exe:
        print(f"Found {turboctl_exe}, activating.")
    else:
        cfgTuning['use_turboctl']=False
        if use_turboctl is True:
            print("Warning: Failed to find 'turboctl', cpu turbo not disabled during benchmarking.")

    if use_cpupower and cpupower_exe:
            print(f"Found {cpupower_exe}, activating.")
    else:
        cfgTuning['use_cpupower']=False
        if use_cpupower is True:
            print("Warning: Failed to find 'cpupower', cpu scaling not disabled during benchmarking.")

    # Detect 'chrt', fallback to 'nice'
    if use_prio:
        chrt_exe = shutil.which('chrt')
        nice_exe = shutil.which('nice')
        if chrt_exe:
            print(f"Found {chrt_exe}, activating.")
            cmdprefix = f"{chrt_exe} -f 99"
        elif nice_exe:
            print(f"Found {nice_exe}, activating.")
            cmdprefix = f"{nice_exe} -n -20"
        elif use_prio is True:
            print("Warning: Failed to find 'chrt' or 'nice', cpu priority not set.")

    # Detect 'perf'
    if use_perf and perf_exe:
        print(f"Found {perf_exe}, activating.")
        cmdprefix += f" {perf_exe} stat -e cpu-clock:u -o '{timefile}' -- "
        mode = 'perf'
    else:
        # Fallback to 'time' if found
        if time_exe:
            print(f"Found {time_exe}, activating.")
            timeformat="%U"
            cmdprefix += f" {time_exe} -o '{timefile}' -f '{timeformat}' -- "
            mode = 'time'

        if use_perf is True and time_exe:
            print("Warning: Failed to find 'perf' util, falling back to less accurate 'time' for cputime measurements.")
        else:
            print("Warning: Failed to find 'perf' and 'time' util, unable to accurately measure elapsed cputime.")
            mode = 'python'

    return mode

def cputweak(enable):
    ''' Disable turbo, disable idlestates, and set fixed cpu mhz. Requires sudo rights. '''
    # Turn off cpu turbo and power savings
    if enable:
        if cfgTuning['use_turboctl']:
            runcommand(f"sudo {turboctl_exe} off", silent=1)
        if cfgTuning['use_cpupower']:
            runcommand(f"sudo {cpupower_exe} frequency-set -g performance --min {cfgTuning['cpu_bench_speed']*1000} --max {cfgTuning['cpu_bench_speed']*1000}", silent=1)
            runcommand(f"sudo {cpupower_exe} idle-set -D 2", silent=1)

    # Turn cpu turbo and power savings back on
    if not enable:
        if cfgTuning['use_turboctl']:
            runcommand(f"sudo {turboctl_exe} on")
        if cfgTuning['use_cpupower']:
            runcommand(f"sudo {cpupower_exe} frequency-set --min {cfgTuning['cpu_std_minspeed']*1000} --max {cfgTuning['cpu_std_maxspeed']*1000}")
            runcommand(f"sudo {cpupower_exe} idle-set -E")

def findfile(filename,fatal=True):
    ''' Search for filename in CWD, homedir and deflatebench.py-dir '''
    tmpCwd = os.path.normpath(os.path.join( os.getcwd(), filename))
    tmpHome = os.path.normpath(os.path.join( os.path.expanduser("~"), filename))
    filepath = os.path.dirname(os.path.realpath(__file__))
    tmpScript = os.path.normpath(os.path.join(filepath, '../', filename))
    if os.path.isfile(tmpCwd):
        return os.path.realpath(tmpCwd)
    elif os.path.isfile(tmpHome):
        return os.path.realpath(tmpHome)
    elif os.path.isfile(tmpScript):
        return os.path.realpath(tmpScript)

    if fatal:
        print(f"Unable to find file: '{filename}'")
        sys.exit(1)
    return None

def hashfile(file):
    ''' Calculate hash of file '''
    sha1 = hashlib.sha1()

    with open(file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def generate_testfile(sourcefile,destfile,minsize):
    ''' Make tempfiles that are concatenated repeatedly until the file is big enough '''
    srcsize = os.path.getsize(sourcefile)
    if srcsize == 0:
        print(f"Error: Sourcefile '{sourcefile}' is empty, cannot generate testfiles.")
        sys.exit(1)

    count = math.ceil((minsize*1024*1024)/srcsize)
    dstsize = srcsize*count

    dst = open(destfile, "wb")
    with open(sourcefile, 'rb') as src:
        while os.path.getsize(destfile) < dstsize:
            data = src.read(BUF_SIZE)
            if not data:
                src.seek(0)
                continue
            dst.write(data)
    dst.close()

def parse_timefile(filen):
    ''' Parse output from perf or time '''
    if cfgConfig['use_perf']:
        with open(filen) as f:
            content = f.readlines()
        for line in content:
            if line[-13:-1] == 'seconds user':
                return float(line[:-13])
        return 0.0
    else:
        with open(filen) as f:
            content = f.readlines()
        return float(content[0])

def runcommand(command, env=None, stoponfail=1, silent=1, output=os.devnull):
    ''' Run command, and handle special cases '''
    env = env if env else None
    args = shlex.split(command, posix=sys.platform != 'win32')
    sp_args = {}
    if sys.platform == 'win32':
        sp_args['creationflags'] = subprocess.HIGH_PRIORITY_CLASS
    if silent == 1:
        devnull = open(output, 'w')
        retval = subprocess.call(args,env=env,stdout=devnull,**sp_args)
        devnull.close()
    else:
        retval = subprocess.call(args,env=env,**sp_args)
    if (retval != 0) and (stoponfail != 0):
        sys.exit(f"Failed, retval({retval}): {command}")
    return retval
