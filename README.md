## deflatebench -  a tool that can benchmark minigzip/minideflate

* This tool must be run from the folder where an executable `minigzip` or `minideflate` exist.
* Ex: `../deflatebench/deflatebench.py --gen`
* You must provide the tool with testdata files.

### Config Files
* `--write` parameter creates a new config file as ~/deflatebench.conf
* Supports profiles in separate config files
* Supports overriding config files with command-line parameters

### System Tuning
<sub>PS: Several of these require root or sudo permissions</sub>
* Supports `perf` or `time` for measuring cputime [Default perf]
* Supports `chrt` to set real-time priority [Default ON]
* Supports `nosync` library preloading [Default ON]
* Supports `turboctl` for disabling cpu turbo while benchmarking [Default ON]
* Supports `cpupower` for locking cpu speed and disabling powersaving while benchmarking [Default ON]
  * `cpu_minspeed` configures normal minimal cpu speed in Mhz to reset back to after benchmark [Default 1000]
  * `cpu_maxspeed` configure minimal cpu speed to use while benchmarking, should be same as cpu normal non-turbo max speed [Default 2000]

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
