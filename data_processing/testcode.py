import sunrise
from datetime import datetime, timezone

start = datetime(year=2019,month=5,day=1,tzinfo=timezone.utc)
end = datetime(year=2021,month=6,day=6,tzinfo=timezone.utc)
directory = r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\Processed"

# sunrise.throughflow(start,end,directory)
a = sunrise.parse_ASV(r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\underway_data\kayak_status_UBOX04.txt",start,end)
sunrise.ASVSurface_png({"test": a},start,end,directory)
