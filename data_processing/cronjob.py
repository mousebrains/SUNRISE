import time
import yaml
from datetime import datetime, timezone, timedelta
import os

# Job file template
template_file = "cronjob_template.yml"

# Plot file
plot_file = 'cronjob_plot.py'

# OUTPUT directory
OUTPUT_DIR = "/home/pat/Processed/Rolling-2Days"

# log job_file
clog = OUTPUT_DIR + "/clog.txt"
clog_f = open(clog, 'w')

# Print current time
CURRENT_TIME = datetime.now().replace(tzinfo=timezone.utc)
timestamp = '------------------------Current Time: %s------------------------\n' \
      % (CURRENT_TIME.isoformat())
print(timestamp)
_ = clog_f.write(timestamp)

# Set time window
#END_TIME = datetime.now().replace(tzinfo=timezone.utc)
# for testing
END_TIME = datetime(2021,6,11,0,0,0,tzinfo=timezone.utc)

START_TIME = END_TIME - timedelta(days=2)

# Make job file
job_file = OUTPUT_DIR + "/crobjob-%s.yml" % datetime.now().strftime("%Y-%m-%dT%H-%M")
os.system("sed -e 's/#START_TIME#/%s/g' -e 's/#END_TIME#/%s/g' %s > %s" \
                % (START_TIME.isoformat(), END_TIME.isoformat(), template_file, job_file))

# Plot
try:
    os.system('python3 %s %s' % (plot_file, job_file))
    msg = "Done!"
    print(msg)
    _ = clog_f.write(msg)
except:
    errmsg = "Error! Restart in %04d seconds" % sleep_time
    print(errmsg)
    _ = clog_f.write(errmsg)
    
# Remove job file
os.system('rm %s' % job_file)

