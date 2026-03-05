Scheduling DET Runs
===================

Scheduling the Data Export Tool to run at regular intervals keeps your
database up to date with CommCare HQ.

For detailed scheduling instructions (including Windows Task Scheduler
setup), see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Configuring-DET-to-Run-as-a-Scheduled-Task-on-Windows).


Quick Reference
---------------

Sample scripts are provided in the `examples/` directory:

- **Windows**: `examples/scheduled_run_windows.bat` -- use with
  [Task Scheduler](https://sqlbackupandftp.com/blog/how-to-schedule-a-script-via-windows-task-scheduler/)
- **Linux/Mac**: `examples/scheduled_run_linux.sh` -- use with
  [cron](https://www.techtarget.com/searchdatacenter/definition/crontab)

### Linux/Mac Setup

1. Copy the example script:
   ```shell
   cp ./examples/scheduled_run_linux.sh ~/scheduled_run_linux.sh
   ```

2. Edit with your project details:
   ```shell
   nano ~/scheduled_run_linux.sh
   ```

3. Add a cron job (runs every 12 hours in this example):
   ```shell
   crontab -e
   ```
   ```
   0 */12 * * * bash ~/scheduled_run_linux.sh
   ```

Use [crontab.guru](https://crontab.guru/) to generate custom cron
schedules.


Best Practices
--------------

- Use API keys instead of passwords in scheduled scripts
- Use SQL output format to leverage automatic checkpoints
- Use `--log-dir` to specify a log directory for troubleshooting
- Test manually before scheduling
