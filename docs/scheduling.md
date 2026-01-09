Scheduling DET Runs
===================

*Part of [Technical Documentation](index.md)*

Scheduling the DET (Data Export Tool) to run at regular intervals is a
useful tactic to keep your database up to date with CommCare HQ.

For detailed instructions and best practices, see the
[User Documentation on Scheduling](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET).


Quick Reference
---------------

### Windows

On Windows systems, use the
[Task Scheduler](https://sqlbackupandftp.com/blog/how-to-schedule-a-script-via-windows-task-scheduler/)
to run scheduled scripts.

**Example script:** `examples/scheduled_run_windows.bat`

**Setup steps:**
1. Copy `examples/scheduled_run_windows.bat` to a desired location
2. Edit the file with your project details and credentials
3. Follow the
   [Task Scheduler guide](https://sqlbackupandftp.com/blog/how-to-schedule-a-script-via-windows-task-scheduler/)
   to create a scheduled task

### Linux/Mac

On Linux and Mac systems, use
[cron](https://www.techtarget.com/searchdatacenter/definition/crontab)
to create scheduled jobs.

**Example script:** `examples/scheduled_run_linux.sh`

**Setup steps:**

1. Copy the example script to your home directory:
   ```shell
   cp ./examples/scheduled_run_linux.sh ~/scheduled_run_linux.sh
   ```

2. Edit the file with your details:
   ```shell
   nano ~/scheduled_run_linux.sh
   ```

3. Create a cron job:
   ```shell
   crontab -e
   ```

4. Add an entry (example runs at top of every 12th hour):
   ```
   0 12 * * * bash ~/scheduled_run_linux.sh
   ```

**Cron schedule tool:** Use [crontab.guru](https://crontab.guru/) to
generate and interpret cron schedules.


Best Practices
--------------

1. **Use API keys** instead of passwords in scheduled scripts
2. **Store credentials securely** - use environment variables or secure
   credential storage
3. **Use SQL output format** for scheduled exports to leverage
   checkpoints
4. **Monitor logs** - use `--log-dir` to specify a log directory for
   troubleshooting
5. **Test manually first** before scheduling
6. **Start with longer intervals** (e.g., daily) and decrease if needed
7. **Handle failures gracefully** - checkpoints will resume from last
   success


Checkpoint Benefits
-------------------

When using SQL output format, checkpoints provide:

- **Automatic incremental updates** - Only new/modified data is exported
- **Resume after failures** - If an export fails, the next run continues
  from the last successful point
- **Faster execution** - Less data to process on each run
- **Reduced API load** - Fewer requests to CommCare HQ


Example Scheduled Command
-------------------------

```shell
# Export forms incrementally to PostgreSQL database
commcare-export \
  --commcare-hq https://www.commcarehq.org \
  --username user@example.com \
  --api-key YOUR_API_KEY \
  --project myproject \
  --query /path/to/query.xlsx \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb \
  --log-dir /path/to/logs
```


See Also
--------

- [Database Integration](database-integration.md) - SQL output and
  checkpoints
- [User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/) -
  Complete scheduling guide
- [Example Scripts](../examples/) - Template scripts for Windows and
  Linux
