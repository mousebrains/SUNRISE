import netCDF4
import numpy as np
import pandas as pd
import datetime
import glob

def write_nc(nc, fields, timestart = datetime.datetime(2021,1,1)):
    """
    LUT:
     0 Date -> 21 April
     1 Time -> 2021 11:01:37
     2 GPS1 Lat -> 25 44.4050
     3 Dir -> N
     4 Lon -> 80 11.0299
     5 Dir -> W
     6 SOG Knots -> 6.5
     7 COG Deg. True -> 353.3
     8 Lat Dec. Deg. -> + 25.7401
     9 Lon Dec. Deg. -> - 80.1838
    10 GPS2 Lat -> 25 44.4058
    11 Dir -> N
    12 Lon -> 80 11.0341
    13 Dir -> W
    14 SOG Knots -> 6.6
    15 COG Deg. True -> 355.7
    16 Lat Dec. Deg. -> + 25.7401
    17 Lon Dec. Deg. -> - 80.1839
    18 Gyro -> 355.67
    19 Water Speed F/A Spd. Knots -> 0.0
    20 P/S Spd. Knots -> 0.0
    21 PIR w/m^2 -> 451.1
    22 PSP w/m^2 -> 1.4
    23 TUV w/m^2 -> 2.0
    24 Rain Gauge Cond. Code -> Empty
    25 Inst. Precip. mm/hr -> 0.0
    26 Accum. Precip. mm -> 0.0
    27 Depth Feet -> 8.6
    28 Meters -> 2.6
    29 Fathoms -> 1.4
    30 Fluorometer Reading Volts -> 0.19615
    31 Gain -> 30X
    32 DisOrgMat Reading Volts -> 1.68406
    33 Gain -> 30X
    34 MAYBE TEMP? -> 27.0942
    35 POSMV Lat -> 25 44.4058
    36 Dir -> N
    37 Lon -> 80 11.0341
    38 Dir -> W
    39 SOG Knots -> 6.6
    40 COG Degrees T -> 356.0
    41 Lat Dec. Deg. -> + 25.7401
    42 Lon Dec. Deg. -> - 80.1839
    43 POSMV Heading Degrees T -> 359.10
    44 RM Young Barometer mb -> Empty
    45 Stbd RM Young Winds Rel. Wind Spd. Knots -> 7.0
    46 Rel. Wind Dir. Degrees -> 67.0
    47 True Wind Spd. Knots -> 8.0
    48 True Wind Dir. Degrees -> 116.5
    49 Port RM Young Met Air Temp. Degrees C -> 24.5
    50 Rel. Humid. % -> 81.0
    51 Baro. Press. mb -> 1015.0
    52 MicroTSG1MicroTSG Temperature Degrees C -> 27.3552
    53 MicroTSG Conductivity Seimens -> 5.4785
    54 MicroTSG Salinity PSU -> 34.4867
    55 Turner C7 -> 92.32
    56 Empty -> 137.92
    57 Empty -> 203.92
    58 Depth -> 0.00
    59 Temp C -> 27.13
    """

    tidx = nc.dimensions["time"].size

    new_time = datetime.datetime.strptime(fields[0] + fields[1], "%d %B%Y %H:%M:%S")
    nc['Date'][tidx] = (new_time-timestart).total_seconds()

    nc['Lon'][tidx] = -float(fields[37].split()[0])+float(fields[37].split()[1])/60.
    nc['Lat'][tidx] = float(fields[35].split()[0])+float(fields[35].split()[1])/60.
    nc['Heading'][tidx] = float(fields[43])
    nc['Depth'][tidx] = float(fields[28])
    nc['Temperature'][tidx] = float(fields[59])
    nc['Salinity'][tidx] = float(fields[54])
    nc['Conductivity'][tidx] = float(fields[53])
    nc['AirTemp'][tidx] = float(fields[49])
    nc['BaroPressure'][tidx] = float(fields[51])
    nc['RelHumidity'][tidx] = float(fields[50])
    nc['WindDirection'][tidx] = float(fields[48])
    nc['WindSpeed'][tidx] = float(fields[47]) * 0.514444

    print("Appending -> ")
    print(netCDF4.num2date(nc['Date'][-1], nc['Date'].units))


def read_new(csv_names, nc_name, skip=2, spacing=60):
    # get the last date
    nc = netCDF4.Dataset(nc_name, 'r+')
    try:
        last_date = netCDF4.num2date(nc['Date'][-1], nc['Date'].units,\
        only_use_cftime_datetimes=False)
    except:
        last_date = datetime.datetime(2021,6,22,23,59,0)

    print("Last record -> ")
    print(last_date)

    # get new data
    for csv_name in csv_names:
        with open(csv_name, "r") as fp:

            # Skip the first 2 lines
            for _ in range(skip):
                next(fp)

            # Find time window
            line = fp.readline().strip() # Strip off whitespace
            fields = line.split("\t") # Split by tabs
            fields = list(map(lambda x: x.strip(), fields))
            time_start_csv = datetime.datetime.strptime(fields[0] + fields[1], "%d %B%Y %H:%M:%S")
            time_end_csv = datetime.datetime.strptime(fields[0] + fields[1], "%d %B%Y %H:%M:%S") \
                            + datetime.timedelta(days=1)

            # Read data
            if (last_date<time_start_csv):
                write_nc(nc, fields)
                cnt = 0
                for line in fp:
                    cnt+=1
                    if cnt%spacing==0:
                        line = line.strip() # Strip off whitespace
                        fields = line.split("\t") # Split by tabs
                        fields = list(map(lambda x: x.strip(), fields))
                        write_nc(nc, fields)

                last_date = netCDF4.num2date(nc['Date'][-1], nc['Date'].units,\
                        only_use_cftime_datetimes=False)

            elif (last_date>=time_start_csv) & (last_date<time_end_csv):
                cnt = 0
                for line in fp:
                    cnt+=1
                    if cnt%spacing==0:
                        line = line.strip() # Strip off whitespace
                        fields = line.split("\t") # Split by tabs
                        fields = list(map(lambda x: x.strip(), fields))
                        new_time = datetime.datetime.strptime(fields[0] + fields[1], "%d %B%Y %H:%M:%S")
                        if new_time>last_date:
                            write_nc(nc, fields)

                last_date = netCDF4.num2date(nc['Date'][-1], nc['Date'].units,\
                        only_use_cftime_datetimes=False)

            else:
                continue

    nc.close()


if __name__ == "__main__":
    csv_names = glob.glob("/mnt/GOM/VIDS/Lister/*WS21163_Hetland-Dly*")
    nc_name = '/home/pat/Dropbox/WaltonSmith/FTMET/WS_FTMET_1min.nc'
    read_new(csv_names, nc_name)
