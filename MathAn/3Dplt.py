import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt



from sqlalchemy import create_engine
eng = create_engine('postgresql+psycopg2://sa:11111111@10.3.18.56:5432/tdxStocks')

df = pd.read_sql('600180', eng).tail(100).reset_index(drop=True).reset_index()

#时间转换
df['data'] = pd.to_datetime(df.datetime).dt.strftime('%Y%m%d')
x = df['index']
y = df.close
z = df.vol
fig = plt.figure()
ax = fig.add_axes(rect=(0, 0.05, 0.95, 0.95), projection='3d')

ax.scatter()
ax.plot_surface(x, y, z, rstride=1, cstride=1, cmap='RdBu_r', vmin=-0.5, vmax=0.5)
ax.set_xlabel('X')
ax.set_ylabel('Y')
# ax.set_xticks(np.arange(-1, 1.1, 0.5))
# ax.set_yticks(np.arange(-1, 1.1, 0.5))
ax.set_zlabel('Z')
plt.show()





import matplotlib.pyplot as plt
import numpy as np

# Fixing random state for reproducibility
np.random.seed(19680801)


fig = plt.figure()
ax = fig.add_subplot(projection='3d')
x, y = np.random.rand(2, 100) * 4
hist, xedges, yedges = np.histogram2d(x, y, bins=4, range=[[0, 4], [0, 4]])

# Construct arrays for the anchor positions of the 16 bars.
xpos, ypos = np.meshgrid(xedges[:-1] + 0.25, yedges[:-1] + 0.25, indexing="ij")
xpos = xpos.ravel()
ypos = ypos.ravel()
zpos = 0

# Construct arrays with the dimensions for the 16 bars.
dx = dy = 0.5 * np.ones_like(zpos)
dz = hist.ravel()

ax.bar3d(xpos, ypos, zpos, dx, dy, dz, zsort='average')

plt.show()




from matplotlib import cbook
from matplotlib import cm
from matplotlib.colors import LightSource
import matplotlib.pyplot as plt
import numpy as np

# Load and format data
dem = cbook.get_sample_data('jacksboro_fault_dem.npz', np_load=True)
z = dem['elevation']
nrows, ncols = z.shape
x = np.linspace(dem['xmin'], dem['xmax'], ncols)
y = np.linspace(dem['ymin'], dem['ymax'], nrows)
x, y = np.meshgrid(x, y)

region = np.s_[5:50, 5:50]
x, y, z = x[region], y[region], z[region]

# Set up plot
fig, ax = plt.subplots(subplot_kw=dict(projection='3d'))

ls = LightSource(270, 45)
# To use a custom hillshading mode, override the built-in shading and pass
# in the rgb colors of the shaded surface calculated from "shade".
rgb = ls.shade(z, cmap=cm.gist_earth, vert_exag=0.1, blend_mode='soft')
surf = ax.plot_surface(x, y, z, rstride=1, cstride=1, facecolors=rgb,
                       linewidth=0, antialiased=False, shade=False)

plt.show()



from sklearn import preprocessing
scaler = preprocessing.StandardScaler().fit(X_train)
preprocessing.minmax_scale
preprocessing.maxabs_scale
preprocessing.robust_scale
preprocessing.normalize
preprocessing.scale


fig, ax = plt.subplots()
ax.scatter(delta1[:-1], delta1[1:], c=close, s=volume, alpha=0.5)


ax.scatter(df['index'], df.close, s=preprocessing.minmax_scale(df.vol)*100, alpha=0.5)


surf = ax.plot_surface(x, y, z, rstride=1, cstride=1, facecolors=rgb,
                       linewidth=0, antialiased=True, shade=True)




from scipy import fft 
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



prices = df.close
fft = np.fft.fft(prices)


freqs = np.fft.fftfreq(prices.size)
plt.plot(freqs, np.abs(fft))
plt.xlabel('Frequency')
plt.ylabel('Amplitude')
plt.show()

ifft = np.fft.ifft(fft)

plt.plot(prices, label='Original')
plt.plot(ifft.real, label='Reconstructed')
plt.legend()
plt.show()

