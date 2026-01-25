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

BUF_SIZE = 1024*1024  # lets read stuff in 1MB chunks when hashing or copying

def init(inConfig, inTuning):
    ''' Initialize variables '''
    global cfgConfig, cfgTuning
    cfgConfig = inConfig
    cfgTuning = inTuning

def get_env(bench=False):
    ''' Build dict of environment variables '''
    env = dict()
    if bench and cfgTuning['use_nosync']:
        env['LD_PRELOAD'] = '/usr/lib64/nosync/nosync.so'
    return env

def printsysinfo():
    ''' Print system information '''
    uname = platform.uname()
    print(f"OS: {uname.system} {uname.release} {uname.version} {uname.machine}")
    print(f"CPU: {platform.processor()}")

def cputweak(enable):
    ''' Disable turbo, disable idlestates, and set fixed cpu mhz. Requires sudo rights. '''
    # Turn off cpu turbo and power savings
    if enable:
        if cfgTuning['use_turboctl']:
            runcommand('sudo /usr/bin/turboctl off', silent=1)
        if cfgTuning['use_cpupower']:
            runcommand(f"sudo /usr/bin/cpupower frequency-set -g performance --min {cfgTuning['cpu_bench_speed']*1000} --max {cfgTuning['cpu_bench_speed']*1000}", silent=1)
            runcommand('sudo /usr/bin/cpupower idle-set -D 2', silent=1)

    # Turn cpu turbo and power savings back on
    if not enable:
        if cfgTuning['use_turboctl']:
            runcommand('sudo /usr/bin/turboctl on')
        if cfgTuning['use_cpupower']:
            runcommand(f"sudo /usr/bin/cpupower frequency-set --min {cfgTuning['cpu_std_minspeed']*1000} --max {cfgTuning['cpu_std_maxspeed']*1000}")
            runcommand('sudo /usr/bin/cpupower idle-set -E')

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
