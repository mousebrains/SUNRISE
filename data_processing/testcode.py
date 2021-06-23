import sunrise
from datetime import datetime, timezone
import argparse
import yaml

start = datetime(year=2021,month=6,day=22,tzinfo=timezone.utc)
end = datetime(year=2021,month=6,day=23,tzinfo=timezone.utc)
directory = r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\Processed"

# sunrise.throughflow(start,end,directory)
# a = sunrise.parse_ASV(r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\underway_data\kayak_status_UBOX04.txt",start,end)
# sunrise.ASVSurface_png({"test": a},start,end,directory)

# parser = argparse.ArgumentParser()
# parser.add_argument("fn", nargs="+", help="Input yaml files")
# args = parser.parse_args()
#
# for fn in args.fn:
#     with open(fn, "r") as fp:
#         input = yaml.safe_load(fp)
#
# print(input)

P_FT = sunrise.parse_PFT(r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\Pelican\MIDAS_001.elg",start,end)
WS_FT = sunrise.parse_WFT(r"C:\Users\hildi\Documents\Stanford\Research\Sunrise\WS\WS21163_Hetland-Full Vdl",start,end)
sunrise.Hovmoller_Salinity(P_FT,WS_FT,{},start,end,directory)
