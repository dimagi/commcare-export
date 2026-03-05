Scheduling the DET
------------------
Scheduling the DET to run at regular intervals is a useful tactic to keep your
database up to date with CommCare HQ.

A common approach to scheduling DET runs is making use of the operating systems' scheduling
libraries to invoke a script to execute the `commcare-export` command. Sample scripts can be
found in the `examples/` directory for both Windows and Linux.

### Windows
On Windows systems you can make use of the [task scheduler](https://sqlbackupandftp.com/blog/how-to-schedule-a-script-via-windows-task-scheduler/)
to run scheduled scripts for you.

The `examples/` directory contains a sample script file, `scheduled_run_windows.bat`, which can be used by the
task scheduler to invoke the `commcare-export` command.

To set up the scheduled task you can follow the steps below.
1. Copy the file `scheduled_run_windows.bat` to any desired location on your system (e.g. `Documents`)
2. Edit the copied `.bat` file and populate your own details
3. Follow the steps outlined [here](https://sqlbackupandftp.com/blog/how-to-schedule-a-script-via-windows-task-scheduler/),
using the .bat file when prompted for the `Program/script`.


### Linux
On a Linux system you can make use of the [crontab](https://www.techtarget.com/searchdatacenter/definition/crontab)
command to create scheduled actions (cron jobs) in the system.

The `examples/` directory contains a sample script file, `scheduled_run_linux.sh`, which can be used by the cron job.
To set up the cron job you can follow the steps below.
1. Copy the example file to the home directory
> cp ./examples/scheduled_run_linux.sh ~/scheduled_run_linux.sh
2. Edit the file to populate your own details
> nano ~/scheduled_run_linux.sh
3. Create a cron job by appending to the crontab file
> crontab -e

Make an entry below any existing cron jobs. The example below executes the script file at the top of
every 12th hour of every day
> 0 12 * * * bash ~/scheduled_run_linux.sh

You can consult the [crontab.guru](https://crontab.guru/) tool which is very useful to generate and interpret
any custom cron schedules.
