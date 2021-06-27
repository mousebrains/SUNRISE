import netCDF4
import datetime
import gsw
import csv
import os
import numpy as np
import matplotlib.pyplot as plt

WS_FT = netCDF4.Dataset('/home/pat/Dropbox/WaltonSmith/FTMET/WS_FTMET_1min.nc')
PE_FT = netCDF4.Dataset('/home/pat/Dropbox/Pelican/MIDAS/Pelican_FTMET.nc')

date_WS = netCDF4.num2date(WS_FT['Date'][:], WS_FT['Date'].units, only_use_cftime_datetimes=False)
tidx_WS = np.where(date_WS>(date_WS[-1]-datetime.timedelta(hours=4)))

date_PE = netCDF4.num2date(PE_FT['time'][:], PE_FT['time'].units, only_use_cftime_datetimes=False)
tidx_PE = np.where(date_PE>(date_PE[-1]-datetime.timedelta(hours=4)))

fig = plt.figure(figsize=(16,9))

ax1 = fig.add_subplot(4,2,1)
ax2 = fig.add_subplot(4,2,2, sharex=ax1)
ax3 = fig.add_subplot(4,2,3, sharex=ax1)
ax4 = fig.add_subplot(4,2,4, sharex=ax1)
ax5 = fig.add_subplot(4,2,5, sharex=ax1)
ax6 = fig.add_subplot(4,2,6, sharex=ax1)
ax7 = fig.add_subplot(4,2,7, sharex=ax1)
ax8 = fig.add_subplot(4,2,8, sharex=ax1)

ax1.plot(date_PE[tidx_PE], PE_FT['Temperature'][tidx_PE], label='PE')
ax2.plot(date_PE[tidx_PE], PE_FT['Salinity'][tidx_PE], label='PE')
ax3.plot(date_PE[tidx_PE], PE_FT['Conductivity'][tidx_PE], label='PE')
ax4.plot(date_PE[tidx_PE], PE_FT['AirTemp'][tidx_PE], label='PE')
ax5.plot(date_PE[tidx_PE], PE_FT['BaroPressure'][tidx_PE], label='PE')
ax6.plot(date_PE[tidx_PE], PE_FT['RelHumidity'][tidx_PE], label='PE')
ax7.plot(date_PE[tidx_PE], PE_FT['WindDirection'][tidx_PE], label='PE')
ax8.plot(date_PE[tidx_PE], PE_FT['WindSpeed'][tidx_PE], label='PE')

ax1.plot(date_WS[tidx_WS], WS_FT['Temperature'][tidx_WS], label='WS')
ax2.plot(date_WS[tidx_WS], WS_FT['Salinity'][tidx_WS], label='WS')
ax3.plot(date_WS[tidx_WS], WS_FT['Conductivity'][tidx_WS], label='WS')
ax4.plot(date_WS[tidx_WS], WS_FT['AirTemp'][tidx_WS], label='WS')
ax5.plot(date_WS[tidx_WS], WS_FT['BaroPressure'][tidx_WS], label='WS')
ax6.plot(date_WS[tidx_WS], WS_FT['RelHumidity'][tidx_WS], label='WS')
ax7.plot(date_WS[tidx_WS], WS_FT['WindDirection'][tidx_WS], label='WS')
ax8.plot(date_WS[tidx_WS], WS_FT['WindSpeed'][tidx_WS], label='WS')

ax1.grid()
ax2.grid()
ax3.grid()
ax4.grid()
ax5.grid()
ax6.grid()
ax7.grid()
ax8.grid()
ax8.legend()

ax1.set_ylabel('Temperature [deg C]')
ax2.set_ylabel('Salinity [psu]')
ax3.set_ylabel('mS/cm')
ax4.set_ylabel('Air Temperature [deg C]')
ax5.set_ylabel('Barometer Pressure [mBar]')
ax6.set_ylabel('Relative Humidity [%]')
ax7.set_ylabel('True Wind Direction [degree]')
ax8.set_ylabel('True Wind Speed [m/s]')
ax7.set_xlabel('Time')
ax8.set_xlabel('Time')

plt.tight_layout()
plt.savefig('/home/pat/Dropbox/html/WS_FTMET_data.png', dpi=100)

