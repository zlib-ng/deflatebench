## deflatebench -  a tool that can benchmark minigzip/minideflate

This tool must be run from the folder where an executable `minigzip` or `minideflate` exist.\
Ex: `../deflatebench/deflatebench.py --gen`. (I suggest making a symlink to it though, for example in /usr/bin/)\
You must provide the tool with testdata files.

### Prerequisites

To setup the required Python packages use the following command:

```
python3 -m pip install -r requirements.txt
```

### Config Files
* `--write` parameter creates a new config file as ~/deflatebench.conf
* Supports profiles in separate config files
* Supports overriding config files with command-line parameters

### System Tuning
<sub>PS: Several of these require root or sudo permissions</sub>
* Supports `perf` or `time` for measuring cputime [Default perf]
* Supports `chrt` to set real-time priority [Default OFF]
* Supports `nosync` library preloading [Default OFF]
* Supports `turboctl` for disabling cpu turbo while benchmarking [Default OFF]
  * `turboctl` script included in repo supports disabling turbo with `intel_pstate` cpu-governor, and should be copied do /usr/bin/turboctl and added to sudo config
* Supports `cpupower` for locking cpu speed and disabling powersaving while benchmarking [Default OFF]
  * `cpu_std_minspeed` configures normal minimal cpu speed in Mhz to reset back to after benchmark [Default 1000]
  * `cpu_std_maxspeed` configures normal maxumum (non-Turbo) cpu speed in Mhz to reset back to after benchmark [Default 2200]
  * `cpu_bench_speed` configure cpu speed to use while benchmarking, should be same as cpu normal non-turbo max speed or a little slower(200Mhz for example) [Default 2000]

### Test configuration
* Specify number of testruns [Default 15]
* Specify number of worst results to ignore [Default 5]
* Specify minlevel [Default 0]
* Specify maxlevel [Default 9]
* Specify testtool either minigzip or minideflate [Default minigzip]

### Test modes
* Single, tests all levels using the same testdata-file
* Multi, allows you to specify separate testdata-files per level
* Gen, lets you provide the tool with a single testdata-file, and the tool will generate files of the appropriate sizes (in MiB) according to what is specified under [Testdata_Gen] in the configfile
  * Gen works by concatenating the source file multiple times until the asked for size is met or exceeded.
  * This works best with a relatively small input file. I use a 15MiB file, and let all levels get a generated size that is a multiple of 15MiB.
* Please note that for best performance, the temp folder specified in the config [Default /tmp/] should be tmpfs or ramdisk.

### Example Testdata
As a convenience, I have created a couple uncompressed tar files that can be used for `single` and `gen` testmodes:
* [202MiB full Silesia testcorpus](https://mirror.circlestorm.org/silesia.tar)
* [15MiB custom cropped Silesia testcorpus](https://mirror.circlestorm.org/silesia-small.tar)

The original source of this testcorpus is here: [Silesia](http://sun.aei.polsl.pl/~sdeor/index.php?page=silesia)
