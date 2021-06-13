import csv
import cmocean.cm as cmo
import datetime
import gsw
import sys

from kml_tools import kml_coloured_line

# *************************** PARSE SYSTEM ARGS *************************** #

START = sys.argv[1]
END = sys.argv[2]
WRITE_DIRECTORY = sys.argv[3]

try:
    if START == "None":
        start = datetime.datetime.fromisoformat("2021-06-19T00:00:00+00:00")
    else:
        start = datetime.datetime.fromisoformat(START)
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
except:
    sys.exit("Invalid start time. Start time must be in isoformat: \n" +
        "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

try:
    if END == "None":
        end = datetime.datetime.now(datetime.timezone.utc)
    else:
        end = datetime.datetime.fromisoformat(END)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)
except:
    sys.exit("Invalid end time. End time must be in isoformat: \n" +
        "'YYYY-mm-ddTHH:MM:SS' or 'YYYY-mm-ddTHH:MM:SSzzzzzz'")

try:
    if not os.path.isdir(WRITE_DIRECTORY):
        os.mkdir(WRITE_DIRECTORY)
except:
    sys.exit("Invalid directory path")


# ******************************* SET PATHS ****************************** #

PELICAN_DATAPATH = '../../underway_data/MIDAS_002.elg'
WALTON_SMITH_DATAPATH = '../../underway_data/20210411212WS21111_Baringer-Dly VDL.dat' # '../../underway_data/tpw.dat'
# ASV_1_DATAPATH = ''
# ASV_2_DATAPATH = ''

# ******************************* DENSITY ******************************** #

PRESSURE = 0 # pressure [dbar] at throughflow

def get_sigma0(sal,temp,lon,lat):
    SA = gsw.SA_from_SP(sal,PRESSURE,lon,lat)
    CT = gsw.CT_from_t(SA,temp,PRESSURE)
    return gsw.density.sigma0(SA,CT)

# ******************************* PELICAN ********************************* #

Pelican_latitudes = []
Pelican_longitudes = []
Pelican_times = []
Pelican_salinities = []
Pelican_temperatures = []
Pelican_sigmas = []

with open(PELICAN_DATAPATH, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        time = row["Time"]
        if time[-2:] != "00":
            continue
        date = row["Date"]
        date = datetime.datetime.strptime(date,"%m/%d/%Y")
        time = datetime.time.fromisoformat(time)
        time = datetime.datetime.combine(date, time, tzinfo=datetime.timezone.utc)
        if time > end:
            break
        if time < start:
            continue

        lat = row["ADU800-GGA-Lat"]
        Pelican_latitudes.append(float(lat[0:2]) + float(lat[2:-1])/60)
        lon = row["ADU800-GGA-Lon"]
        Pelican_longitudes.append(-1*float(lon[0:3]) - float(lon[3:-1])/60)

        Pelican_times.append(time)

        temp = row["Thermosalinograph-Data-Temp"]
        if not temp:
            # Handle empty temperature field
            temp = "nan"
        try:
            Pelican_temperatures.append(float(temp))
        except:
            print("Unexpected Temperature Value")
            Pelican_temperatures.append(float("nan"))

        sal = row["Thermosalinograph-Data-Salinity"]
        if not sal:
            # Handle empty salinity field
            sal = "nan"
        try:
            Pelican_salinities.append(float(sal))
        except:
            print("Unexpected Salinity Value")
            Pelican_salinities.append(float("nan"))

        try:
            sigma0 = get_sigma0(float(sal), float(temp),
                Pelican_longitudes[-1], Pelican_latitudes[-1])
        except:
            sigma0 = float("nan")
        Pelican_sigmas.append(sigma0)

# *************************** WALTON SMITH ******************************** #

WS_latitudes = []
WS_longitudes = []
WS_times = []
WS_salinities = []
WS_temperatures = []
WS_sigmas = []

with open(WALTON_SMITH_DATAPATH, 'r') as f:
    next(f)
    header_string = next(f)
    header = header_string.split("\t")

    line_1 = next(f)
    line_1_values = line_1.split("\t")

    line_2 = next(f)
    line_2_values = line_2.split("\t")


    for a,b,n in zip(header,line_1_values,range(1000)):
        print(f"{n}: {a} {b}")

# kml_coloured_line(WRITE_DIRECTORY,
#     "Pelican_Salinity",
#     Pelican_salinities,
#     Pelican_longitudes,
#     Pelican_latitudes,
#     Pelican_times,
#     cmo.deep,
#     "Pelican Salinity")
#
# kml_coloured_line(WRITE_DIRECTORY,
#     "Pelican_Temperature",
#     Pelican_temperatures,
#     Pelican_longitudes,
#     Pelican_latitudes,
#     Pelican_times,
#     cmo.thermal,
#     "Pelican Temperature")
#
# kml_coloured_line(WRITE_DIRECTORY,
#     "Pelican_Density",
#     Pelican_sigmas,
#     Pelican_longitudes,
#     Pelican_latitudes,
#     Pelican_times,
#     cmo.dense,
#     "Pelican Density")
