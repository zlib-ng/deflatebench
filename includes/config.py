""" config.py -- Helperfunctions related to reading/writing deflatebench config files.

    Copyright (C) Hans Kristian Rosbach

    This software is provided under the Zlib License.
    See the included LICENSE file for details.
"""
import tempfile
import toml

def defconfig():
    ''' Define default config '''
    config = dict()
    config['Testruns'] = {  'runs': 15,
                            'trimworst': 5,
                            'minlevel': 0,
                            'maxlevel': 9,
                            'strategies': '', # fhRF
                            'testmode': 'single',  # generate / multi / single
                            'testtool': 'minigzip' } # minigzip / minideflate

    config['Config'] = {'temp_path': tempfile.gettempdir(),
                        'use_perf': True,
                        'start_delay': 0,   # Milliseconds of startup to skip measuring, requires usleep(X*1000) in minigzip/minideflate main()
                        'skipverify': False,
                        'skipdecomp': False}

    ## CPU related settings
    config['Tuning'] = {'use_chrt': False,
                        'use_nosync': False,
                        'use_turboctl': False,
                        'use_cpupower': False,
                        'cpu_std_minspeed': 1000,
                        'cpu_std_maxspeed': 2200,
                        'cpu_bench_speed': 2000 }

    # Single testfile
    config['Testdata_Single'] = { 'testfile': 'silesia.tar' }

    # Multiple testfiles
    config['Testdata_Multi'] = {'0': 'testfile-500M',
                                '1': 'testfile-300M',
                                '2': 'testfile-150M',
                                '3': 'testfile-125M',
                                '4': 'testfile-100M',
                                '5': 'testfile-85M',
                                '6': 'testfile-75M',
                                '7': 'testfile-40M',
                                '8': 'testfile-20M',
                                '9': 'testfile-20M' }

    # Generated testfiles
    config['Testdata_Gen'] =  { 'srcFile': 'silesia-small.tar',
                                '0': 500,
                                '1': 270,
                                '2': 135,
                                '3': 105,
                                '4': 90,
                                '5': 90,
                                '6': 75,
                                '7': 60,
                                '8': 45,
                                '9': 45 }
    return config

def parseconfig(file):
    ''' Parse config file '''
    config = toml.load(file)
    return config

def writeconfig(file):
    ''' Write default config to file '''
    config = defconfig()
    with open(file, 'w') as f:
        toml.dump(config,f)

def mergeconfig(src, chg):
    ''' Merge config settings from chg into src '''
    if 'Testruns' in chg:
        src['Testruns'].update(chg['Testruns'])
    if 'Config' in chg:
        src['Config'].update(chg['Config'])
    if 'Tuning' in chg:
        src['Tuning'].update(chg['Tuning'])
    if 'Testdata_Gen' in chg:
        src['Testdata_Gen'].update(chg['Testdata_Gen'])
    if 'Testdata_Single' in chg:
        src['Testdata_Single'].update(chg['Testdata_Single'])
    if 'Testdata_Multi' in chg:
        src['Testdata_Multi'].update(chg['Testdata_Multi'])
    return src
