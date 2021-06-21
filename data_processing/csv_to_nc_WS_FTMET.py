import netCDF4
import numpy as np
import pandas as pd
import datetime


def read_new(csv_name, nc_name, skip=1, hdrFix=True):
    # get old data size
    nc = netCDF4.Dataset(nc_name, 'r')
    skip_old = nc.dimensions["time"].size
    nc.close()

    # creat new df
    df = pd.DataFrame()
    with open(csv_name, "r") as fp:
        hdr = None
        seen = set()

        # Skip the first line
        for _ in range(skip):
            next(fp)


        # Read headers
        line = fp.readline().strip() # Strip off whitespace
        fields = line.split("\t") # Split by tabs
        fields = list(map(lambda x: x.strip(), fields))

        if hdr is None:
            hdr = []
            for item in fields:
                if len(item):
                    if hdrFix:
                        if item == "POSMV Lat":
                            hdr.append("MAYBE TEMP?")
                        elif item == "RM Young Barometer mbStbd RM Young Winds Rel. Wind Spd. Knots":
                            hdr.append("RM Young Barometer mb")
                            item = "Stbd RM Young Winds Rel. Wind Spd. Knots"
                    while item in seen: item += "X"
                    seen.add(item)
                    hdr.append(item)
                else: # Empty item
                    if not hdrFix or len(hdr) not in [58]:
                        item = "Empty"
                        while item in seen: item += "X"
                        seen.add(item)
                        hdr.append(item)


        # Skip old data
        for _ in range(skip_old):
            next(fp)

        # read new data
        for line in fp:
            line = line.strip() # Strip off whitespace
            fields = line.split("\t") # Split by tabs
            fields = list(map(lambda x: x.strip(), fields))
            item = pd.Series(fields, index=hdr[:len(fields)])
            df = df.append(item, ignore_index=True)

    return df, skip_old


def append_to_nc(csv_name, nc_name, timestart = datetime.datetime(2021,1,1,tzinfo=datetime.timezone.utc)):
    df, skip_old = read_new(csv_name, nc_name)
    nc_new = netCDF4.Dataset(nc_name, 'r+')

    for tidx in range(df.shape[0]):
        nc_new['Lon'][skip_old+tidx] = -float(df["Lon Dec. Deg.XX"][tidx].split()[-1])
        nc_new['Lat'][skip_old+tidx] = float(df["Lat Dec. Deg.XX"][tidx].split()[-1])
        nc_new['Heading'][skip_old+tidx] = float(df['POSMV Heading Degrees T'][tidx])
        nc_new['Depth'][skip_old+tidx] =  float(df['Meters'][tidx])
        nc_new['Temperature'][skip_old+tidx] = float(df["MicroTSG1MicroTSG Temperature Degrees C"][tidx])
        nc_new['Salinity'][skip_old+tidx] = float(df['MicroTSG Salinity PSU'][tidx])
        nc_new['Conductivity'][skip_old+tidx] = float(df['MicroTSG Conductivity Seimens'][tidx])
        nc_new['AirTemp'][skip_old+tidx] = float(df['Port RM Young Met Air Temp. Degrees C'][tidx])
        nc_new['BaroPressure'][skip_old+tidx] = float(df['Baro. Press. mb'][tidx])
        nc_new['RelHumidity'][skip_old+tidx] = float(df['Rel. Humid. %'][tidx])
        nc_new['WindDirection'][skip_old+tidx] = float(df['True Wind Dir. Degrees'][tidx])
        nc_new['WindSpeed'][skip_old+tidx] = float(df['True Wind Spd. Knots'][tidx]) * 0.514444

        newtime=datetime.datetime.strptime(df['Date'][tidx] + df['Time'][tidx], "%d %B%Y %H:%M:%S").\
                        replace(tzinfo=datetime.timezone.utc)
        nc_new['Date'][skip_old+tidx] = (newtime-timestart).total_seconds()

    nc_new.close()


if __name__ == "__main__":
    csv_name = '../../../WaltonSmith_test/FT/WS21111_Baringer-Full Vdl.dat'
    nc_name = '../../WS_FTMET.nc'
    append_to_nc(csv_name, nc_name)
