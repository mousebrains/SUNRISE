import time
import yaml
from datetime import datetime, timezone, timedelta
import os
import subprocess

# Job file template
template_file = "/home/pat/SUNRISE/data_processing/cronjob_template.yml"

# Plot file
plot_file = '/home/pat/SUNRISE/data_processing/realtime.py'

# OUTPUT directory
OUTPUT_DIR = "/home/pat/Processed/Rolling-2Days"

# log job_file
clog = OUTPUT_DIR + "/clog.txt"
clog_f = open(clog, 'a')

# Print current time
CURRENT_TIME = datetime.now().replace(tzinfo=timezone.utc)
timestamp = '------------------------Current Time: %s------------------------\n' \
      % (CURRENT_TIME.isoformat())
print(timestamp)
_ = clog_f.write(timestamp)

# Set time window
END_TIME = datetime.now().replace(tzinfo=timezone.utc)
# for testing
# END_TIME = datetime(2021,6,17,0,0,0,tzinfo=timezone.utc)

START_TIME = END_TIME - timedelta(days=2)

# Make job file
job_file = OUTPUT_DIR + "/crobjob-%s.yml" % datetime.now().strftime("%Y-%m-%dT%H-%M")
os.system("sed -e 's/#START_TIME#/%s/g' -e 's/#END_TIME#/%s/g' %s > %s" \
                % (START_TIME.isoformat(), END_TIME.isoformat(), template_file, job_file))


# Plot
try:
    # print time
    msg = "Time window: %s -> %s\n" % (START_TIME.isoformat(), END_TIME.isoformat())
    print(msg)
    _ = clog_f.write(msg)

    # make plots
    cmd = ["/usr/bin/python3", plot_file, job_file]
    process = subprocess.run(cmd, shell=False, check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    universal_newlines=True)
    print(process.stdout)
    print('Done!\n')
    _ = clog_f.write(process.stdout)
    _ = clog_f.write('Done!\n')
    #os.system('python3 %s %s' % (plot_file, job_file))
except:
    errmsg = "Error! Retry in 30 minutes\n"
    print(errmsg)
    _ = clog_f.write(errmsg)

# Remove job file
os.system('rm %s' % job_file)
