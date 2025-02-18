"""
Author: Shawn Zamperini
Email:  zamp@utk.edu
Date:   9/9/19

This script started with some code written by Jake Nichols, but has moved on
to be it's own standalone script. It provides a framework to plot OEDGE output
data, mostly found in the netCDF file. There is also the capability to plot
data from the collector_probe file as well. The script oedge_plots_gui acts
as an interface to this class full of functions, though there is nothing
stopping someone from using this script on it's own.

List of functions:

__init__
  - Initiate an OedgePlots object by passing in the path to the NetCDF file.

add_dat_file
  - Pass in the path to the .dat file. The GUI should automatically find it if
      it's in the same folder as the NetCDF file.

read_data_2d
  - Read data from the NetCDF file into a form easily manipulated for plotting
      in plot_contour_polygon.

read_data_2d_kvhs
  - Same as above, but uses the .dat file to add on an additional, ad-hoc
      flow velocity (option T13 and associated parameters).

get_sep
  - Creates lines for plotting the separatrix in plot_contour_polygon.

calculate_forces
  - DIVIMP does not seem to output the forces in a meaningful way yet, so instead
      we just recalculate them here. Returns in a 2D form that can be used in
      plot_contour_polygon.

plot_contour_polygon
  - The primary function in this script. This is the one that creates the 2D plots
      of whatever you want from the NetCDF file, as well as the above mentioned
      plots that require a bit more data. There are many input parameters to change,
      so it's a very flexible function. Users of the GUI just get a plug-n-play
      usage of it.

cp_plots
  - Plots the impurity fluence at the locations of the collector probes. Could use
      some TLC in updating.

plot_lp_input
  - Not implemented yet.

create_ts
  - Loads Thomson scattering data from atlas and puts it in an Excel file format
      that can be used later. This is used in comparing TS data to the OEDGE
      background data, and can take a while to run sometimes.

compare_ts
  - This one uses data created from the above function and creates a PDF of
      comparisons.

check_ts
  - Helper function to make sure the TS data after being mapped to a common
      flux surface looks reasonable.

find_ring_knot
  - Helper function to find which ring, knot a given R, Z location is on.

fake_probe
  - See what a hypothetical probe (Langmuir, Mach) inserted into the plasma
      would look like.

along_ring
  - Choose a ring number and plot some data along it from target to target.
      Requires the variable name form the NetCDF file currently.
"""

import netCDF4
import numpy             as np
import matplotlib        as mpl
import matplotlib.pyplot as plt
import pandas            as pd
from collections         import OrderedDict
from matplotlib.backends.backend_pdf import PdfPages


# A nice looking font.
#plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.family'] = 'DejaVu Sans'

# These are the "Tableau 20" colors as RGB.
tableau20 = [(31, 119, 180), (174, 199, 232), (255, 127, 14), (255, 187, 120),
             (44, 160, 44), (152, 223, 138), (214, 39, 40), (255, 152, 150),
             (148, 103, 189), (197, 176, 213), (140, 86, 75), (196, 156, 148),
             (227, 119, 194), (247, 182, 210), (127, 127, 127), (199, 199, 199),
             (188, 189, 34), (219, 219, 141), (23, 190, 207), (158, 218, 229)]

# Scale the RGB values to the [0, 1] range, which is the format matplotlib accepts.
for i in range(len(tableau20)):
    r, g, b = tableau20[i]
    tableau20[i] = (r / 255., g / 255., b / 255.)

# Create class object to hold in netcdf data as well as plotting routines. Use
# Ordered Dict prototype so we can index the class object with the data name.
# Ex: self['BTS']
class OedgePlots:

    def __init__(self, netcdf_path):
        """
        Initialization for class object. Loads in the relevant netCDF variables
        needed for the plots.

        netcdf_path: Path location of .nc file.
        """

        # Load in the netCDF file.
        self.nc = netCDF4.Dataset(netcdf_path)
        self.ncpath = netcdf_path

        # Initialize variable to hold dat file.
        self.dat_file = None

        # Load in some netCDF data that is used a lot.
        self.rs     = self.nc['RS'][:]
        self.zs     = self.nc['ZS'][:]
        self.nrs    = self.nc['NRS'][:]
        self.nks    = self.nc['NKS'][:]
        self.area   = self.nc['KAREAS'][:]
        self.korpg  = self.nc['KORPG'][:]
        self.rvertp = self.nc['RVERTP'][:]
        self.zvertp = self.nc['ZVERTP'][:]
        self.rvesm  = self.nc['RVESM'][:]
        self.zvesm  = self.nc['ZVESM'][:]
        self.irsep  = self.nc['IRSEP'][:]
        self.qtim   = self.nc['QTIM'][:]
        self.kss    = self.nc['KSS'][:]
        self.kfizs  = self.nc['KFIZS'][:]
        self.ksmaxs = self.nc['KSMAXS'][:]
        self.irsep  = self.nc['IRSEP'][:]
        self.irwall = self.nc['IRWALL'][:]
        self.crmb   = self.nc['CRMB'][:]
        self.crmi   = self.nc['CRMI'][:]
        self.emi    = 1.602E-19
        self.cion   = self.nc['CION'][:]

        try:
            self.absfac = self.nc['ABSFAC'][:]
        except:
            print("Warning: Can't load all variables from NetCDF file (okay if DIVIMP was not run).")

        # Create a mesh of of the corners of the each cell/polygon in the grid.
        #mesh  = np.array([])
        mesh = []
        num_cells = 0

        # Scan through the rings.
        for ir in range(self.nrs):

            # Scan through the knots.
            for ik in range(self.nks[ir]):

                # Get the cell index of this knot on this ring.
                index = self.korpg[ir,ik] - 1

                # Only if the area of this cell is not zero append the corners.
                if self.area[ir,ik] != 0.0:
                    vertices = list(zip(self.rvertp[index][0:4], self.zvertp[index][0:4]))
                    #mesh = np.append(mesh, vertices)
                    mesh.append(vertices)
                    num_cells = num_cells + 1

                    # Print out a warning is the cell center is not within the vertices.
                    cell = mpl.path.Path(list(vertices))
                    r = self.rs[ir, ik]
                    z = self.zs[ir, ik]
                    if not cell.contains_point([r, z]):
                        print("Error: Cell center not within vertices.")
                        print("  (ir, ik)    = ({}, {})".format(ir, ik))
                        print("  Vertices    = {}".format(vertices))
                        print("  Cell center = ({}, {})".format(r, z))

        # Save the results in the class.
        self.num_cells = num_cells
        self.mesh = mesh

    def __repr__(self):
        message = 'OedgePlots Object\n' + \
                  '  Title:       ' + self.nc['TITLE'][:].data.tostring().decode('utf-8') + '\n' + \
                  '  Date Run:    ' + self.nc['JOB'][:].data.tostring().strip()[:8].decode('utf-8') + '\n' + \
                  '  Grid:        ' + self.nc['EQUIL'][:].data.tostring().decode('utf-8') + '\n' + \
                  '  A Cool Dude: You\n' + \
                  '  Description: ' + self.nc['DESC'][:].data.tostring().decode('utf-8') + '\n'

        return message

    def add_dat_file(self, dat_path):
        """
        Quick function to read in the dat_file into the class. The file is not
        suitible for pandas or anything like that, so just read it in as a text
        with newlines at the end of each line.

        dat_path: Path location of .dat file.
        """
        self.datpath = dat_path
        with open(dat_path) as f:
            self.dat_file = f.read()

    def read_data_2d(self, dataname, charge=None, scaling=1.0, fix_fill=False, no_core=False):
        """
        Reads in 2D data into a 1D array, in a form that is then passed easily
        to PolyCollection for plotting.

        dataname : The 2D data as named in the netCDF file.
        charge   : The charge state to be plotted, if applicable.
        scaling  : Scaling factor to apply to the data, if applicable. Secret
                     option is 'Ring' to just return the ring number at each cell.
        fix_fill : Swap out the default huge number that it seems is put in when
                     there is no data with just a zero. Better for plotting.
        """

        # Get the 2D data from the netCDF file. Some special options included.
        # Normalized s coordinate of each cell.
        if dataname == 'Snorm':
            raw_data = self.nc['KSB'][:] / self.ksmaxs[:, None]
            raw_data = np.abs(raw_data + raw_data / 1.0 - 1.0)
        else:
            raw_data = self.nc[dataname][:]

        data = np.zeros(self.num_cells)

        # 'all' just sums up all charge states. So here instead of loop for speed.
        if charge == 'all':
            raw_data = raw_data.sum(axis=0)

        count = 0
        for ir in range(self.nrs):
            for ik in range(self.nks[ir]):
                if self.area[ir, ik] != 0.0:

                    # Just make the data the ring number.
                    if scaling == 'Ring':
                        data[count] = ir
                    else:

                        # If charge is specifed, this will be the first dimension,
                        # and will need to charge + 1 to match index.
                        if charge in [None, 'all']:
                            data[count] = raw_data[ir][ik] * scaling
                        else:
                            data[count] = raw_data[charge + 1][ir][ik] * scaling

                        # If we don't want the core data in the plot, then let's
                        # replace it with just None.
                        if no_core:
                            if ir < self.irsep - 1:
                                #data[count] = None
                                data[count] = 0.0
                    count = count + 1

        # This will fix an issue where the netCDF will fill in values (that are
        # maybe outside the normal grid?) with 9.99E36. Swap these out with zeros
        # if desired.
        if fix_fill:
            fill_val = data.max()
            data[np.where(data == fill_val)] = None

        return data

    def read_data_2d_kvhs_t13(self, no_core=False):
        """
        Special function for plotting the flow velocity. This
        is because some DIVIMP options (T13, T31, T37?, T38?...) add
        additional flow values not reflected in KVHS. These
        additional values are in the .dat file, and thus it is required to run
        this function.
        """

        # Make sure .dat file has been loaded.
        if self.dat_file == None:
            print("Error: .dat file not loaded in. Run 'add_dat_file' first.")

        try:
            pol_opt = float(self.dat_file.split('POL DRIFT OPT')[1].split(':')[0])
            if pol_opt == 0.0:
                print("Error: Poloidal drift option T13 was not on for this run.")
                return -1

            # Get the relevant table for the extra drifts out of the .dat file.
            add_data = self.dat_file.split('TABLE OF DRIFT REGION BY RING - RINGS ' + \
                                            'WITHOUT FLOW ARE NOT LISTED\n')[1]. \
                                            split('DRIFT')[0].split('\n')

            # Split the data between the spaces, put into DataFrame.
            add_data = [line.split() for line in add_data]
            add_df = pd.DataFrame(add_data[1:-1], columns=['IR', 'Vdrift (m/s)',
                                  'S_START (m)', 'S_END (m)'], dtype=np.float64). \
                                  set_index('IR')

            # Get the 2D data from the netCDF file.
            dataname = 'KVHS'
            scaling = 1.0 / self.qtim
            raw_data = self.nc[dataname][:]
            data = np.zeros(self.num_cells)

            # Convert the 2D data (ir, ik) into 1D for plotting in the PolyCollection
            # matplotlib function.
            count = 0
            for ir in range(self.nrs):
                for ik in range(self.nks[ir]):
                    if self.area[ir, ik] != 0.0:

                        # Put the data from this [ring, knot] into a 1D array.
                        data[count] = raw_data[ir][ik] * scaling

                        # If this ring has additional drifts to be added.
                        if ir in add_df.index:

                            # Then add the drift along the appropriate s (or knot) range.
                            if self.kss[ir][ik] > add_df['S_START (m)'].loc[ir] and \
                               self.kss[ir][ik] < add_df['S_END (m)'].loc[ir]:

                               data[count] = data[count] + add_df['Vdrift (m/s)'].loc[ir]

                        # If we don't want the core data in the plot, then let's
                        # replace it with just None.
                        if no_core:
                            if ir < self.irsep - 1:
                                #data[count] = None
                                data[count] = 0.0

                        count = count + 1

            return data

        except IndexError:
            print('Error: Was T13 on for this run?')
            return None

    def get_sep(self):
        """
        Return collection of lines to be plotted with LineCollection method
        of matplotlib for the separatrix.
        """

        # Get (R, Z) coordinates of separatrix.
        rsep = self.rvertp[self.korpg[self.irsep-1,:self.nks[self.irsep-1]]][:,0]
        zsep = self.zvertp[self.korpg[self.irsep-1,:self.nks[self.irsep-1]]][:,0]
        nsep = len(rsep)
        lines=[]

        # Construct separatrix as a series of pairs of coordinates (i.e. a line
        # between the coordinates), to be plotted. Don't connect final point to first.
        for i in range(nsep-2):
            lines.append([(rsep[i], zsep[i]), (rsep[i+1], zsep[i+1])])

        return lines

    def calculate_forces(self, force, vz_mult = 0.0, charge=None, no_core=False, imp_amu=183.84):
        """
        Return 2D representations of the parallel forces (FF, FiG, FeG, FPG, FE)
        in the same format as read_data_2d for easy plotting. This data is not
        returned in the NetCDF file, so we calculate it here. Ideally we would
        use exactly what DIVIMP calculates, but that doesn't seem to be here yet.

        force   : One of 'FF', 'FiG', 'FeG', 'FPG', 'FE' or 'Fnet' (to sum
                  them all).
        charge  : Charge of impurity ion needed for some of the forces.
        vz_mult : Fraction of the background velocity used for vz (needed only
                  in FF).
        no_core :
        imp_amu : The Mass in AMU of the impurity to be followed (default is W).
                    Carbon is 12.01 AMU.
        """

        # Temperature and density values for calculations.
        te = self.read_data_2d('KTEBS', no_core=no_core)
        ti = self.read_data_2d('KTIBS', no_core=no_core)
        ne = self.read_data_2d('KNBS',  no_core=no_core)
        col_log = 15
        qe      = 1.602E-19
        amu_kg  = 1.66E-27
        fact = np.power(self.qtim, 2) * qe / (imp_amu * amu_kg)

        # See if T13 was on. Important for FF calculations.
        try:
            pol_opt = float(self.dat_file.split('POL DRIFT OPT')[1].split(':')[0])
            if pol_opt == 0.0:
                t13 = False
            elif pol_opt == 1.0:
                print("Additional poloidal drift option T13 was ON.")
                t13 = True

        except:
            print("Warning: Unable to determine if T13 was on/off. Possible .dat \
                   file was not loaded?")

        # Friction force calculations.
        if force.lower() in ['ff', 'fnet']:

            # Slowing down time.
            try:
                tau_s = 1.47E13 * self.crmi * ti * np.sqrt(ti / self.crmb) / \
                        ((1 + self.crmb / self.crmi) * ne * np.power(charge, 2) * col_log)

                #print("FF:  {:.2f} s".format(tau_s))
            except TypeError:
                print("Error: Charge of ion needed for FF calculation.")
                return None

            # TODO: Currently will assume impurity velocity is some fraction of the
            # background velocity (default zero), though this is obviously not true
            # and a better implementation would use the real values wherever they are.
            # This would require having the velocity distribution of the impurities.
            if t13:
                vi = self.read_data_2d_kvhs_t13()
            else:

                # Don't forget KVHS is scaled by 1/QTIM to get m/s.
                scaling = 1.0 / self.qtim
                vi = self.read_data_2d('KVHS', scaling=scaling, no_core=no_core)

            vz = vz_mult * vi

            # Calculate the force.
            ff = self.crmi * amu_kg * (vi - vz) / tau_s

            # If not 'fnet', then go ahead and return.
            if force.lower() == 'ff':
                return ff

        # TODO: Pressure gradient force calculations.
        if force.lower() in ['fpg', 'fnet']:

            # Parallel collisional diffusion time.
            #tau_par = 1.47E13 * self.crmi * ti * np.sqrt(ti / self.crmb) / \
            #          (ne * np.power(charge, 2) * col_log)

            # Need to probably figure this out.
            fpg = 0

            # If not 'fnet', then go ahead and return.
            if force.lower() == 'fpg':
                return fpg

        # Electron temperature gradient force calculations.
        if force.lower() in ['feg', 'fnet']:
            alpha = 0.71 * np.power(charge, 2)

            # The electron temperature gradient from the code. I don't understand
            # this scaling factor, but Jake uses it to get into presumably eV/m.
            kfegs = self.read_data_2d('KFEGS', scaling = qe / fact, no_core=no_core)

            # Calculate the force.
            feg = alpha * kfegs

            # If not 'fnet', then go ahead and return.
            if force.lower() == 'feg':
                return feg

        # Ion temperature gradient force calculations.
        if force.lower() in ['fig', 'fnet']:
            mu = self.crmi / (self.crmi + self.crmb)
            beta = 3 * (mu + 5 * np.sqrt(2) * np.power(charge, 2) * \
                   (1.1 * np.power(mu, 5/2) - 0.35 * np.power(mu, 3/2)) - 1) / \
                   (2.6 - 2 * mu + 5.4 * np.power(mu, 2))
            print("FiG: Beta = {:.2f}".format(beta))

            # Again, must scale the gradient with this scaling factor.
            kfigs = self.read_data_2d('KFIGS', scaling = qe / fact, no_core=no_core)

            # Calculate the force.
            fig = beta * kfigs

            # If not 'fnet', then go ahead and return.
            if force.lower() == 'fig':
                return fig

        # Electric field force calculations.
        if force.lower() in ['fe', 'fnet']:

            # This also gets scaled by a factor as well in Jake's code.
            e_pol = self.read_data_2d('E_POL', scaling = qe / fact, no_core=no_core)
            fe = charge * qe * e_pol

            # If not 'fnet', then go ahead and return.
            if force.lower() == 'fe':
                return fe

        # Net force calculation.
        if force.lower() == 'fnet':
            return ff + fpg + feg + fig + fe

    def plot_contour_polygon(self, dataname, charge=None, scaling=1.0,
                             normtype='linear', cmap='plasma', xlim=[0.9, 2.5],
                             ylim = [-1.5, 1.5], plot_sep=True, levels=None,
                             cbar_label=None, fontsize=16, lut=21,
                             smooth_cmap=False, vmin=None, vmax=None,
                             show_cp=None, ptip=None, show_mr=False,
                             fix_fill=False, own_data=None, no_core=False, vz_mult=0.0):

        """
        Create a standalone figure using the PolyCollection object of matplotlib.
        This is the main function here for plotting 2D data, and you should be
        able to control most whatever you want through the options since this
        was made to be a versatile function.

        dataname:    The netCDF variable name to plot. Some special datanames
                       will perform extra data handling: KVHSimp, ...
        charge:      The charge state to be plotted, if applicable.
        scaling:     Scaling factor to apply to the data, if applicable.
        normtype:    One of 'linear', 'log', ... of how to normalize the data on
                       the plot.
        cmap:        The colormap to apply to the plot. Uses standard matplotlib
                       names.
        xlim:        X range of axes.
        ylim:        Y range of axes.
        plot_sep:    Include separatrix on plot or not.
        levels:      Number of levels for colorbar (needs work).
        cbar_label:  Label for the colorbar.
        fontsize:    Size of font for labels.
        lut:         Number of chunks to break the colormap into.
        smooth_cmap: Choose whether to break colormap up into chunks or not.
        vmin/vmax:   Option to choose own vmin, vmax for the colorbars. Useful
                       when plots need tweaking.
        show_cp:     Choose if collector probes are to be shown. Can have
                       multiple probes as a list. 1 = MiMES, 2 = Top, 3 = DiMES.
        ptip:        The tip (either R or Z, depends on which probe you picked)
                       of the probe. Can pass as list where each entry corresponds
                       to the one in show_cp.
        show_mr:     Option to show the metal rings or not from MRC-I.
        fix_fill:    The defaults for some masked_arrays is to fill in blank
                       values with 1e36. I think zero is more appropriate for
                       plotting correctly.
        own_data:    Bring your own data to work day. This could be used if you
                     want to plot the ratio of two data point or something. So if
                     you wanted to ratio of two datasets returned by read_data_2d,
                     then you could say own_data = data1 / data2.
        no_core:     Don't include data in the core region.
        vz_mult:     An optional input for if you're plotting the friction force.
                       See calculate_forces for more info.
        """

        # Make sure show_cp and ptip is in list form if not.
        #if show_cp != None:
        if type(show_cp) is not list:
            show_cp = [show_cp]
        if type(ptip) is not list:
            ptip = [ptip]

        # Option to provide own dataset from read_data_2d, say like a ratio
        # between two of them or something that you calculated ahead of itme.
        if own_data is not None:
            data = own_data

        # Get the data through normal means.
        else:

            # Read in the data into a form for PolyCollection. Account for special
            # options.
            # Flow velocity with additional velocity specified by T13.
            if dataname == 'KVHSimp':
                data = self.read_data_2d_kvhs_t13(no_core=no_core)
                #if data == -1:
                #    return None

            # Special option to plot the ring numbers.
            elif dataname == 'Ring':
                data = self.read_data_2d('KTEBS', scaling='Ring', no_core=no_core)

            # Divide the background velocity by the sounds speed to get the Mach number.
            elif dataname == 'KVHSimp - Mach':
                te   = self.read_data_2d('KTEBS', no_core=no_core)
                ti   = self.read_data_2d('KTIBS', no_core=no_core)
                kvhs = self.read_data_2d_kvhs_t13()
                mi   = self.crmb * 931.494*10**6 / (3e8)**2  # amu --> eV s2 / m2
                cs   = np.sqrt((te + ti) / mi)
                data = kvhs / cs  # i.e. the Mach number.

            elif dataname == 'KVHS - Mach':
                te   = self.read_data_2d('KTEBS', no_core=no_core)
                ti   = self.read_data_2d('KTIBS', no_core=no_core)
                kvhs = self.read_data_2d('KVHS',  no_core=no_core, charge=charge,
                                         scaling=scaling, fix_fill=fix_fill)
                mi   = self.crmb * 931.494*10**6 / (3e8)**2  # amu --> eV s2 / m2
                cs   = np.sqrt((te + ti) / mi)
                print("CRMB = {} amu".format(self.crmb))
                data = kvhs / cs  # i.e. the Mach number.

            # Special function for plotting the forces on impuirties.
            elif dataname.lower() in ['ff', 'fig', 'feg', 'fpg', 'fe', 'fnet']:

                # Need to reorganize so we can do the t13 flag and vz_mult.
                data = self.calculate_forces(dataname, charge=charge,
                                             no_core=no_core, vz_mult=vz_mult)

            # Everything else in the netCDF file.
            else:
                data = self.read_data_2d(dataname, charge, scaling, fix_fill, no_core)

        # Remove any cells that have nan values.
        not_nan_idx = np.where(~np.isnan(data))[0]
        #not_nan_idx = np.where(~np.isnan(data))
        mesh = np.array(self.mesh)[not_nan_idx, :, :]
        data = data[not_nan_idx]

        # Create a good sized figure with correct proportions.
        fig = plt.figure(figsize=(7, 9))
        ax  = fig.add_subplot(111)

        if normtype == 'linear':
            if vmin == None:
                vmin = data.min()
            if vmax == None:
                vmax = data.max()
            norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

        elif normtype == 'log':
            data[data == 0.0] = 1e-3
            if vmin == None:
                vmin = data.min()
            if vmax == None:
                vmax = data.max()
            norm = mpl.colors.LogNorm(vmin=vmin, vmax=vmax)

        elif normtype == 'symlin':
            if vmin == None:
                vmin = -np.abs(data).max()
            if vmax == None:
                vmax = -vmin
            norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
            cmap = 'coolwarm'

        elif normtype == 'symlog':
            data[data == 0.0] = 1e-3
            if vmin == None:
                vmin = -np.abs(data[~np.isnan(data)]).max()
            if vmax == None:
                vmax = -vmin
            norm = mpl.colors.SymLogNorm(linthresh=0.01 * vmax, vmin=vmin, vmax=vmax)
            cmap = 'coolwarm'

        # Choose whether to discretize the colormap or not first.
        if smooth_cmap:
            scalar_map = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
        else:
            scalar_map = mpl.cm.ScalarMappable(norm=norm, cmap=mpl.cm.get_cmap(cmap, lut=lut))

        # Create PolyCollection object.
        coll = mpl.collections.PolyCollection(mesh, array=data,
                                              cmap=scalar_map.cmap,
                                              norm=scalar_map.norm,
                                              edgecolors='none')

        # Add the PolyCollection to the Axes object.
        ax.add_collection(coll)
        ax.plot(self.rvesm, self.zvesm, color='k', linewidth=1)

        # Get the separatrix coordinates as a collection of lines and plot.
        if plot_sep:
            sep = self.get_sep()
            sc = mpl.collections.LineCollection(sep, color='k')
            ax.add_collection(sc)

        # Use correct amount of levels for colorbar, if specified.
        if levels is not None:
            cbar = fig.colorbar(coll, ax=ax, boundaries=levels, ticks=levels)
        else:
            cbar = fig.colorbar(coll, ax=ax, extend='both')

        # Add colorbar label.
        if cbar_label is None:
            cbar.ax.set_ylabel(dataname, fontsize=fontsize)
        else:
            cbar.ax.set_ylabel(cbar_label, fontsize=fontsize)

        # Option to add collector probes to plots.
        if show_cp:
            if ptip == None:
                print("Error: Location of tip of probe not given.")

        # MiMES probe.
        cp_width  = 0.03
        facecolor = 'grey'
        edgecolor = 'black'
        if 1 in show_cp:
            ptip_tmp = ptip[show_cp.index(1)]
            lower_xy = (ptip_tmp, -0.185 - cp_width/2.0)
            width    = 2.38 - ptip_tmp
            height   = cp_width
            rect = mpl.patches.Rectangle(lower_xy, width=width, height=height,
                                         facecolor=facecolor, edgecolor=edgecolor)
            ax.add_patch(rect)

        # Top crown probe. Point is to simulate a DiMES probe if it were USN.
        if 2 in show_cp:
            ptip_tmp = ptip[show_cp.index(2)]
            lower_xy = (1.485 - cp_width/2.0, ptip_tmp)
            width    = cp_width
            height   = ptip_tmp - 1.172
            rect = mpl.patches.Rectangle(lower_xy, width=width, height=-height,
                                         facecolor=facecolor, edgecolor=edgecolor)
            ax.add_patch(rect)

        # DiMES probe.
        if 3 in show_cp:
            ptip_tmp = ptip[show_cp.index(3)]
            lower_xy = (1.485 - cp_width/2.0, -1.25)
            width    = cp_width
            height   = ptip_tmp - (-1.25)
            rect = mpl.patches.Rectangle(lower_xy, width=width, height=height,
                                         facecolor=facecolor, edgecolor=edgecolor)
            ax.add_patch(rect)

        # Option to show metal rings. Floor (1.32-1.37) Shelf (1.404, 1.454).
        if show_mr:
            tile_height = 0.01
            facecolor   = 'red'
            edgecolor   = 'black'
            floor_xy    = (1.32, -1.363 - tile_height)
            floor_width = 1.37 - 1.32
            shelf_xy    = (1.404, -1.250 - tile_height)
            shelf_width = 1.454 - 1.404
            floor_rect  = mpl.patches.Rectangle(floor_xy, width = floor_width,
                                               height=tile_height,
                                               facecolor=facecolor,
                                               edgecolor=edgecolor)


            shelf_rect  = mpl.patches.Rectangle(shelf_xy, width = shelf_width,
                                               height=tile_height,
                                               facecolor=facecolor,
                                               edgecolor=edgecolor)
            ax.add_patch(floor_rect)
            ax.add_patch(shelf_rect)

        # Organize plot, add labels.
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_xlabel('R (m)', fontsize=fontsize)
        ax.set_ylabel('Z (m)', fontsize=fontsize)
        fig.tight_layout()
        fig.show()

        return fig

    def cp_plots(self, cp_path, xaxis='ROMP', yaxis='IMPFLUX', cp_num=1,
                 fontsize=16, log=False, print_to_file=False):
        """
        Plot some of the collector probe data. Note: This still requires work,
        namely with the crown (top) probe.

        cp_path:      Path to the .collector_probe file.
        xaxis:        Which column name to plot on the xaxis.
        yaxis:        Which column name to plot on the yaxis, excluding the _IDF, _ODF.
                         One of IMPFLUX or IMPDENS
        cp_num:        1 = midplane probe, 2 = crown probe.
        fontsize:      Font size for the plots.
        log:           Set to true to use a log y axis.
        print_to_file: Print output to file in directory of netCDF file for
                         external use.
        """

        # Open files and read all the lines in.
        with open(cp_path) as f:
            lines = np.array(f.readlines())

        # If there is another cp on this file it will start after two \n's.
        for i in range(len(lines) - 1):
            if lines[i] == '\n':
                if lines[i+1] == '\n':
                    next_cp_idx = i

        # Grab the ABSFAC for the scaling.
        absfac = np.float(lines[6].split('     ')[1])

        # Load first cp as DataFrame.
        df1 = pd.read_csv(cp_path, skiprows=7, nrows=next_cp_idx-8, sep=' ',
                         skipinitialspace=True)

        # The INDEX column on the file doesn't have numbers under it so it goofs
        # up he df with an extra NaN column. Fix real quick.
        correct_cols = df1.columns[1:]
        df1 = df1.drop(df1.columns[-1], axis=1)
        df1.columns = correct_cols

        # Read in the second probe if there is one.
        df2 = pd.read_csv(cp_path, skiprows=8+next_cp_idx, sep=' ',
                          skipinitialspace=True)
        correct_cols = df2.columns[1:]
        df2 = df2.drop(df2.columns[-1], axis=1)
        df2.columns = correct_cols

        # The midplane probe I think.
        if cp_num == 1:
            x = df1[xaxis].values
            y_itf = df1[yaxis + '_IDF'].values
            y_otf = df1[yaxis + '_ODF'].values

        # The crown probe I think.
        elif cp_num == 2:
            x = df2[xaxis].values
            y_itf = df2[yaxis + '_IDF'].values
            y_otf = df2[yaxis + '_ODF'].values

        if xaxis == 'ROMP':
            xlabel = 'R-Rsep OMP (cm)'
            x = x  * 100.0

        if yaxis == 'IMPFLUX':
            ylabel = 'Impurity Flux (m-2 s-1)'
            y_itf = y_itf * absfac
            y_otf = y_otf * absfac

        # Plotting commands.
        red  = (214/255, 39/255, 40/255)
        purp = (148/255, 103/255, 189/255)
        fig = plt.figure()
        ax = fig.add_subplot(111)
        if log:
            ax.semilogy(x, y_itf, label='ITF', lw=5, color=red)
            ax.semilogy(x, y_otf, label='OTF', lw=5, color=purp)
        else:
            ax.plot(x, y_itf, label='ITF', lw=5, color=red)
            ax.plot(x, y_otf, label='OTF', lw=5, color=purp)
        ax.set_xlabel(xlabel, fontsize=fontsize)
        ax.set_ylabel(ylabel, fontsize=fontsize)
        ax.legend(fontsize=fontsize)
        fig.tight_layout()
        fig.show()

        if print_to_file:
            import csv
            filename = cp_path.split('.')[0] + '.txt'
            with open(filename, 'w') as f:
                writer = csv.writer(f, delimiter='\t')
                f.write(xaxis+'\tITF\tOTF\n')
                writer.writerows(zip(x, y_itf, y_otf))

    def plot_lp_input(self):
        """
        May need to find the data in the .lim or .dat file.
        """
        pass

    def create_ts(self, shots, times, ref_time, filename=None, load_all_ts=False):
        """
        Function to create a Thomson scattering file in the correct format for
        comparing to OEDGE results. Outputs an Excel file with the data in a
        form that makes importing it back into a DataFrame easy. Important to
        remember that this TS file only applies to the grid is was generated on!
        Using this Excel file with a different grid will not work!

        shots:         Shots to load TS data for to compare OEDGE against.
        times:         Times of which to load a gfile for. If load_all_ts is set
                         to True, the min and max of these times will be used
                         and will grab all available TS times between from EFIT04.
        ref_time:      Time frame to map all the TS measurements back to.
        write_to_file: Should normally be True.
        filename:      Excel output file with the TS data mapped to S.
        load_all_ts:   Choose whether or not to load ALL the times the TS laser
                         had fired for from EFIT04. This takes a long time to
                         load, but should only need to be used once per
                         output file.
        """

        # Import here instead of top just in case someone is using the GUI and
        # was simply supplied a file. Would mean they don't need atlas access.
        from ThomsonClass import ThomsonClass

        # Okay if one shot is entered, just make it a list so it still runs okay.
        if type(shots) == np.ndarray:
            shots = list(shots)
        elif type(shots) != list:
            shots = [shots]

        # Want the times as floats to be consistent. Two decimal places.
        times = np.array(times, dtype=np.float).round(2)
        ref_time = np.round(np.float(ref_time), 2)

        # Total DataFrame to be returned in Excel file.
        self.s_df_all = pd.DataFrame()

        # Go through one shot at time, loading the TS and mapping to S.
        for shot in shots:

            # Load in TS data, then map it to a reference EFIT time (i.e. the time
            # that the OEDGE grid used).
            self.ts_div = ThomsonClass(shot, 'divertor')
            self.ts_div.load_ts(verbal=False)
            self.ts_core = ThomsonClass(shot, 'core')
            self.ts_core.load_ts(verbal=False)

            # If load_al_ts is True, use ALL the times TS data is available for. This
            # could take a REALLY long time though, so give a warning.
            if load_all_ts:
                print('Warning: Loading all TS times. This could take a long time...')

                # Load in all the times.
                div_times = self.ts_div.ts_dict['temp']['X'].round(2)
                core_times = self.ts_core.ts_dict['temp']['X'].round(2)

                # Restrict to the time range input.
                div_idx  = np.where(np.logical_and(div_times>times.min(), div_times<times.max()))
                core_idx = np.where(np.logical_and(core_times>times.min(), core_times<times.max()))
                div_times  = div_times[div_idx]
                core_times = core_times[core_idx]

                # Choose the closest ref_time if it's not in the actual TS list
                # (which is almost certainly the case).
                ref_idx_core  = np.argmin(np.abs(core_times - ref_time))
                ref_time_core = core_times[ref_idx_core]
                ref_idx_div   = np.argmin(np.abs(div_times - ref_time))
                ref_time_div  = div_times[ref_idx_div]

                # Load the times. This is where we will spend some time loading.
                self.ts_div.map_to_efit(times=div_times, ref_time=ref_time_div)
                self.ts_core.map_to_efit(times=core_times, ref_time=ref_time_core)
                num_rows = (len(div_times) * len(self.ts_div.ref_df.index)) + (len(core_times) * len(self.ts_core.ref_df.index))

            else:

                # Just load TS data with the given times.
                self.ts_div.map_to_efit(times=times, ref_time=ref_time)
                self.ts_core.map_to_efit(times=times, ref_time=ref_time)
                num_rows = len(times) * (len(self.ts_div.ref_df.index) + len(self.ts_core.ref_df.index))

            # Initialize DataFrame to hold the S values for this shot. Filling in the index
            # ahead of time isn't needed, but it is much faster than adding on one
            # row at time.
            self.s_df = pd.DataFrame(columns=('S (m)', 'Te (eV)', 'ne (m-3)', 'Ring', 'Cell', 'System', 'Shot', 'R (m)', 'Z (m)', 'Time'),
                                     index=np.arange(0, num_rows))
            idx = 0

            # For each location at each time...
            for ts_sys in [self.ts_div, self.ts_core]:

                # Choose correct time array if using the actual TS times.
                if load_all_ts:
                    if ts_sys is self.ts_div:
                        times = div_times
                    elif ts_sys is self.ts_core:
                        times = core_times
                    else:
                        print("How did you even get to this error?")

                for time in times:
                    loc_num = 0
                    for loc in ts_sys.ref_df[str(time)]:

                        # .. find the distance between each TS location (already mapped
                        # to a common reference EFIT) and each cell in the DIVIMP grid.
                        dist = np.sqrt((loc[0] - self.rs)**2 + (loc[1] - self.zs)**2)
                        closest_cell = np.where(dist == dist.min())

                        # Grab that cell's s coordinate. Pack it up into our DataFrame.
                        s  = self.kss[closest_cell][0]
                        te = ts_sys.ref_df['Te at ' + str(time)].iloc[loc_num]
                        ne = ts_sys.ref_df['Ne at ' + str(time)].iloc[loc_num]
                        r  = ts_sys.ref_df[str(time)].iloc[loc_num][0]
                        z  = ts_sys.ref_df[str(time)].iloc[loc_num][1]
                        ring = closest_cell[0][0] + 1
                        cell = closest_cell[1][0] + 1
                        self.s_df.iloc[idx] = np.array([s, te, ne, ring, cell, ts_sys.system, shot, r, z, time])
                        idx     += 1
                        loc_num += 1

            # Add this to the overall DataFrame which gets the contribution from each shot.
            self.s_df_all = self.s_df_all.append(self.s_df, ignore_index=True)

        # Make sure the data types of each column are correct.
        self.s_df_all['S (m)']    = self.s_df_all['S (m)'].astype(np.float)
        self.s_df_all['Te (eV)']  = self.s_df_all['Te (eV)'].astype(np.float)
        self.s_df_all['ne (m-3)'] = self.s_df_all['ne (m-3)'].astype(np.float)
        self.s_df_all['Ring']     = self.s_df_all['Ring'].astype(np.int)
        self.s_df_all['Cell']     = self.s_df_all['Cell'].astype(np.int)
        self.s_df_all['System']   = self.s_df_all['System'].astype(np.str)
        self.s_df_all['Shot']     = self.s_df_all['Shot'].astype(np.int)
        self.s_df_all['R (m)']    = self.s_df_all['R (m)'].astype(np.float)
        self.s_df_all['Z (m)']    = self.s_df_all['Z (m)'].astype(np.float)
        self.s_df_all['Time']    = self.s_df_all['Time'].astype(np.float)

        print("Reminder: The 'R OMP' value in the Excel file is calculated " +
                 "off the assumption that the shot was stationary during " +
                 "this time frame. These values are only useful for the core " +
                 "Thomson, since finding them for the divertor is difficult.")


        if filename == None:
            filename = 'ts_mapped_to_s_' + str(shot) + '.xlsx'
        self.s_df_all.to_excel(filename)

        return filename

    def compare_ts(self, ts_filename, rings, show_legend='all', nrows=3,
                   ncols=2, bin_width=1.0, output_file='my_ts_comparison.pdf',
                   rad_bin_width=0.0025, core_sweep_bug_time=None, filter_zeros=True,
                   dashed_rings=True):
        """
        Function to create plots to compare the OEDGE results to Thomson
        scattering. A PDF file is output with all the graphs for each ring.

        ts_filename: The Excel file created from "create_ts" above. Has all the
                     TS data mapped to S.
        rings:       OEDGE rings to compare the TS against.
        show_legend: One of 'all' or 'short'. 'all' will show which shot is
                     which color, and 'short' will only show OEDGE and the
                     average TS values, binned accordinagly with std. dev.
        nrows:       Number of rows of plots for the PDF file.
        ncols:       Number of columns of plots for the PDF file.
        bin_width:   Width of each bin, in meters, to bin the TS data along S
                     into. This makes getting averages and a standard deviation
                     possible, making comparing TS to OEDGE much more meaningful.
        output_file: What the save the PDF as.
        rad_bin_width: Bin width for the R-Rsep OMP plots to bin the TS data into.
        core_sweep_bug_time: Handles a bug in the ThomsonClass script. See
                     explanation in the comment about 15 lines down from here.
        filter_zeros: Get rid of some zeros that aren't real data.
        dashed_rings: Put dashed lines on the plots for every tenth ring.
        """

        # Warning that pops up but is unecessary.
        plt.rcParams.update({'figure.max_open_warning': 0})

        # Load in the DataFrame from Excel file. Could maybe save time by seeing
        # if user already has it loaded in from create_ts above, but meh.
        self.s_df_all = pd.read_excel(ts_filename)
        df = self.s_df_all

        # There is a slight bug in the ThomsonClass script that is fortunately
        # easy to work around (love u pandas). To map to a common reference time,
        # it maps each location to the X-point. This allows 2D graphs with the
        # divertor system, but can make it seem like the core is sweeping a
        # range, when it really isn't. Use this variable to indicate the start
        # of the strike point sweep so we can exclude that core data.
        if core_sweep_bug_time is not None:
            drop_idx = np.logical_and(df['System'] == 'core', df['Time'] > core_sweep_bug_time).values
            df = df.iloc[~drop_idx]

        # Get rid of some random zeros that muck things up.
        if filter_zeros:
            df = df[df['Te (eV)']  > 0.0]
            df = df[df['ne (m-3)'] > 0.0]

        # Variables to keep track of which Axes we are on.
        ngraphs = nrows * ncols
        graph_count = 0

        # Create pdf filename. Open up file to save Figures to.
        pdf_filename = output_file
        with PdfPages(pdf_filename) as pdf:

            # Get the Z of the OMP.
            z0 = self.nc['Z0'][:].data
            r0 = self.nc['R0'][:].data

            # Get Rsep at the OMP.
            sep_ring     = self.nc['IRSEP'][:] - 1  # Subtract 1 for indexing means.
            dist         = np.abs(self.zs[sep_ring] - z0)
            rsepomp_cell = np.where(dist == dist.min())[0]
            rsepomp      = self.rs[sep_ring, rsepomp_cell]

            # Get the Thomson R's and Z's. Only upstream and rings outside IRSEP.
            # Downstream comparisons will have to be with Langmuir probes and
            # the parallel to s graphs that utilize the divertor TS.
            tmp_df  = df[np.logical_and(df['Ring'] >= self.irsep, df['Ring'] < 100)] # Just to stop far rings from goofing up the plot.
            ts_r    = tmp_df[tmp_df['System'] == 'core']['R (m)'].values
            ts_z    = tmp_df[tmp_df['System'] == 'core']['Z (m)'].values
            ts_ring = tmp_df[tmp_df['System'] == 'core']['Ring'].values - 1 # Subtract 1 for indexing means.
            ts_te   = tmp_df[tmp_df['System'] == 'core']['Te (eV)'].values
            ts_ne   = tmp_df[tmp_df['System'] == 'core']['ne (m-3)'].values
            ts_cell = tmp_df[tmp_df['System'] == 'core']['Cell'].values
            ts_romp = np.zeros(len(ts_r))

            # First time will be the ref_time since that's HOW I MADE IT WORK DAMMIT.
            ref_time = tmp_df[tmp_df['System'] == 'core']['Time'].values[0]
            self.tmp_df = tmp_df

            # Find which knot corresponds to the OMP.
            for i in range(0, len(ts_r)):

                # Only want the OMP side, so take cells on the right half of R0.
                omp_side = self.rs[ts_ring[i]] > r0

                dist = np.abs(self.zs[ts_ring[i]][omp_side] - z0)
                omp_cell = np.where(dist == dist.min())[0]
                romp = self.rs[ts_ring[i]][omp_side][omp_cell]

                # Find R-Rsep OMP.
                ts_romp[i] = romp - rsepomp

            # Now need to get the OEDGE values at the OMP.
            more_rings = np.arange(sep_ring, self.irwall)
            oedge_romps = np.array([])
            oedge_teomp = np.array([])
            oedge_neomp = np.array([])

            # Get the R location where core Thomson is taken.
            tmp_df2 = tmp_df[tmp_df['System'] == 'core']
            ts_r_ref = tmp_df2[tmp_df2['Time'] == ref_time]['R (m)'].values[0]

            # Array to hold Romp values for plotting dashed lines for every
            # 10th ring (i.e. 20, 30, 40, ...).
            oedge_ring_dashed = np.array([])
            oedge_ring_romps  = np.array([])

            for i in range(0, len(more_rings)):

                # Get the ring we are interested in.
                ring = more_rings[i]
                #print(ring)

                try:
                    # Get the RminRsep OMP values for these values mapped to the OMP.
                    omp_side = self.rs[ring] > r0
                    dist = np.abs(self.zs[ring][omp_side] - z0)
                    omp_cell = np.where(dist == dist.min())[0]
                    romp = self.rs[ring][omp_side][omp_cell]
                    oedge_romps = np.append(oedge_romps, romp - rsepomp)

                    if ring % 10 == 0:
                        oedge_ring_dashed = np.append(oedge_ring_dashed, int(ring))
                        oedge_ring_romps  = np.append(oedge_ring_romps, romp - rsepomp)

                    # Get the Te, ne values along the R value where TS is taken. Need
                    # to find which cell on this ring this is at. Just to be safe only
                    # grab the portion above the OMP.
                    above_omp = self.zs[ring] > z0
                    dist = np.abs(self.rs[ring][above_omp] - ts_r_ref)
                    close_cell = np.where(dist == dist.min())[0]
                    oedge_teomp = np.append(oedge_teomp, self.nc['KTEBS'][:][ring][above_omp][close_cell])
                    oedge_neomp = np.append(oedge_neomp, self.nc['KNBS'][:][ring][above_omp][close_cell])

                except ValueError:
                    #print("Maybe ring {} isn't to the right of the OMP.".format(ring))
                    pass

            # Sort the OEDGE data for plotting.
            idx = np.argsort(oedge_romps)
            oedge_romps = oedge_romps[idx]
            oedge_teomp = oedge_teomp[idx]
            oedge_neomp = oedge_neomp[idx]

            # Make figures, put them into the PDF.
            fig, axs = plt.subplots(2, 1, sharex=True)
            axs = axs.flatten()

            for data in ['Te', 'ne']:
                if data == 'Te':
                    y = ts_te
                    oedge_y = oedge_teomp
                    graph_num = 0
                else:
                    y = ts_ne
                    oedge_y = oedge_neomp
                    graph_num = 1

                # Bin the Thomson data some to get averages and error bars.
                bins = np.arange(ts_romp.min(), ts_romp.max()+rad_bin_width, rad_bin_width)
                digi = np.digitize(ts_romp, bins)
                bin_means = [y[digi == i].mean() for i in range(1, len(bins))]
                bin_stds = [y[digi == i].std() for i in range(1, len(bins))]
                bin_centers = bins[:-1] + rad_bin_width / 2.0

                line1, = axs[graph_num].plot(ts_romp, y, '.', color='lightgrey', alpha=0.35, zorder=-32)
                line2  = axs[graph_num].errorbar(bin_centers, bin_means, fmt='k.',
                                                 yerr=bin_stds,
                                                 capthick=1.5, capsize=3)
                line3, = axs[graph_num].plot(oedge_romps, oedge_y, 'k')
                axs[graph_num].legend((line2, line3), ('Thomson', 'OEDGE'),
                                        loc='upper center', ncol=3,
                                        bbox_to_anchor=(0.5, 1.1),
                                        fancybox=True, shadow=True)

                # Vertical dashed lines for every 10th ring.
                if dashed_rings:
                    axs[graph_num].vlines(oedge_ring_romps, 0, 1e30, colors='k', linestyles='dashed')

                    # Annotate with the rings number of this line.
                    ann_locs_te = list(zip(oedge_ring_romps-0.001, np.full(len(oedge_ring_romps), 150*0.77)))
                    ann_locs_ne = list(zip(oedge_ring_romps-0.001, np.full(len(oedge_ring_romps), 3e19*0.77)))
                    for i in range(0, len(oedge_ring_dashed)):
                        if graph_num == 0:
                            axs[graph_num].annotate(str(int(oedge_ring_dashed[i])), ann_locs_te[i], bbox=dict(facecolor='white', edgecolor='black'))
                        else:
                            axs[graph_num].annotate(str(int(oedge_ring_dashed[i])), ann_locs_ne[i], bbox=dict(facecolor='white', edgecolor='black'))

            axs[0].set_xlim([0, ts_romp.max() * 1.1])
            axs[0].set_ylim([0, 150])
            axs[1].set_ylim([0, 3e19])
            axs[1].set_xlabel('R-Rsep OMP (m)')
            axs[0].set_ylabel('Te (eV)')
            axs[1].set_ylabel('ne (m-3)')
            fig.tight_layout()
            pdf.savefig(fig, papertype='letter')

            # Make parallel to s graphs. One loop for Te, one loop for ne.
            for oedge_data in ['Te', 'ne']:
                graph_count = 0

                # Go through one ring at a time.
                for ring in rings:

                    # Index only the rows of the DataFrame with that ring.
                    ring_df = df[df['Ring'] == ring]

                    # Use modulo to determine if this ring starts a new fig/pdf page.
                    if graph_count % ngraphs == 0:
                        fig, axs = plt.subplots(nrows, ncols, sharex=False, figsize=(10,8))
                        axs = axs.flatten()

                    # Find what color this shot is from the above shots_enum. Elaborate...
                    color = 6
                    shots = df['Shot'].unique()
                    for shot in shots:

                        # Get only the portion matching this shot.
                        smaller_ring_df = ring_df[ring_df['Shot'] == shot]

                        # Choose correct data for Y axis.
                        if oedge_data == 'Te':
                            y = smaller_ring_df['Te (eV)']
                        if oedge_data == 'ne':
                            y = smaller_ring_df['ne (m-3)']

                        # Plot it with a specific color. 2 because those colors are better.
                        # zorder is needed because of a matplotlib bug where the
                        # errorbars render under these data points, which we don't
                        # want.
                        ls = axs[graph_count].plot(smaller_ring_df['S (m)'], y, '.',
                                                   color=tableau20[color], label=shot,
                                                   alpha=1.0, zorder=-32)
                        color += 1

                        # Prevent going past the size of tableau20 array.
                        if color > 23:
                            color -= 24

                    # Now plot the average value + std. dev. of the TS measurements
                    # with requested binning performed.
                    if oedge_data == 'Te':
                        y = ring_df['Te (eV)']
                    if oedge_data == 'ne':
                        y = ring_df['ne (m-3)']

                    # Bin the s values, get the mean and std of the corresponding y values.
                    if len(ring_df.index) == 0:
                        continue
                    s = ring_df['S (m)']
                    #print('Ring: ' + str(ring))
                    #print('smin: ' + str(s.min()))
                    #print('smax: ' + str(s.max()))

                    # If there is essentially just one bin.
                    if np.abs(s.min() - s.max()) < bin_width:
                        bin_means   = y.mean()
                        bin_stds    = y.std()
                        bin_centers = s.mean()

                    # Else do the binning procedure.
                    else:
                        bins = np.arange(s.min(), s.max()+bin_width, bin_width)
                        digi = np.digitize(s, bins)
                        bin_means = [y[digi == i].mean() for i in range(1, len(bins))]
                        bin_stds = [y[digi == i].std() for i in range(1, len(bins))]
                        bin_centers = bins[:-1] + bin_width / 2.0

                    line1 = axs[graph_count].errorbar(bin_centers, bin_means,
                                                      yerr=bin_stds, fmt='k.',
                                                      capthick=1.5, capsize=3)

                    # Find the rings from the OEDGE simulation now. Ring-1 for indexing.
                    oedge_s  = self.nc['KSS'][:][ring-1].data

                    # Te plots.
                    if oedge_data == 'Te':
                        #axs[graph_count].plot(ring_df['S (m)'], ring_df['Te (eV)'], '.')
                        oedge_dat = self.nc['KTEBS'][:][ring-1].data
                        axs[graph_count].set_ylabel('Te (eV)')

                    # ne plots.
                    if oedge_data == 'ne':
                        #axs[graph_count].plot(ring_df['S (m)'], ring_df['ne (m-3)'], '.')
                        oedge_dat = self.nc['KNBS'][:][ring-1].data
                        axs[graph_count].set_ylabel('ne (m-3)')

                    # Drop some extra zeros that sneak in.
                    keep_idx = np.where(oedge_s != 0.0)[0]
                    oedge_s  = oedge_s[keep_idx]
                    oedge_dat = oedge_dat[keep_idx]

                    # Restrict to the outer half since that's where TS data is.
                    half_idx = np.where(oedge_s > oedge_s.max()/2.0)[0][0]
                    oedge_s  = oedge_s[half_idx:]
                    oedge_dat = oedge_dat[half_idx:]

                    # Add OEDGE data to plot. Note comma after 'line2', because plot
                    # returns two items, but errorbar doesn't.
                    line2, = axs[graph_count].plot(oedge_s, oedge_dat, 'k-')

                    # Extra plot commands.
                    axs[graph_count].text(0.715, 0.8, 'Ring ' + str(ring),
                                          transform=axs[graph_count].transAxes)
                    axs[graph_count].set_xlabel('S (m)')
                    if show_legend == 'all':
                        axs[graph_count].legend(loc='upper center', ncol=3, bbox_to_anchor=(0.5, 1.2), fancybox=True, shadow=True)
                    if show_legend == 'short':
                        axs[graph_count].legend((line1, line2), ('Thomson', 'OEDGE'),
                                                loc='upper center', ncol=3,
                                                bbox_to_anchor=(0.5, 1.1),
                                                fancybox=True, shadow=True)

                    # Reset graph_count once it's time for a new page.
                    if graph_count == ngraphs-1:
                        graph_count = 0
                        fig.tight_layout()
                        #fig.legend(ls, shots)
                        pdf.savefig(fig, papertype='letter')
                        plt.close()
                    else:
                        graph_count += 1

                # Save the last of figures remaining.
                if graph_count != 0:
                    fig.tight_layout()
                    pdf.savefig(fig, papertype='letter')
                    plt.close()

    def check_ts(self, ts_filename, time_cutoff=None):
        """
        This helper function just plots the locations of the Thomson scattering
        points after they have been mapped to a common flux surface. Just to
        make sure everything looks alright. Note if there is a strike point
        sweep it will make it look like the core is sweeping a range as well
        when it really isn't. Chose time_cutoff to indicate start of sweep.
        """

        # Load up a plot. Just do Te, it doesn't really matter what data.
        fig = self.plot_contour_polygon('KTEBS', normtype='log')

        # Get our TS file that has the (R, Z) locations to plot over this fig.
        df = pd.read_excel(ts_filename)

        # Potentially a big problem, but unsure yet. Sweeping allows filling out
        # a 2D divertor space, but the mapping process used in these Thomson
        # files may goof up core measurements during a sweep. This allows
        # excluding core data after a certain time.
        if time_cutoff is not None:
            drop_idx = np.logical_and(df['System'] == 'core', df['Time'] > time_cutoff).values
            df = df.iloc[~drop_idx]

        rs = df['R (m)'].values
        zs = df['Z (m)'].values

        fig.axes[0].plot(rs, zs, 'k.', ms=1)
        fig.show()

    def find_ring_knot(self, r, z):
        """
        This function will return the ring and the knot on that ring of the cell
        closest to the input (r, z). Outputs as (ring, knot) in a tuple.
        """

        dist = np.sqrt((r - self.rs)**2 + (z - self.zs)**2)
        closest_cell = np.where(dist == dist.min())

        return (closest_cell[0][0], closest_cell[1][0])

    def fake_probe(self, r_start, r_end, z_start, z_end, data='Te', num_locs=100, plot=None, fontsize=16):
        """
        Return data, and plot, of a mock probe. Plot is useful if the probe has
        a constant R or Z value, just choose the correct option for it.

        data: One of 'Te', 'ne', 'Mach' or 'Velocity'.
        plot: Either None, 'R' or 'Z' (or 'r' or 'z'), or 'psin'. If the probe is at a
              constant R, then use 'R', likewise for 'Z'.
        """

        # Create rs and zs to get measurements at.
        rs = np.linspace(r_start, r_end, num_locs)
        zs = np.linspace(z_start, z_end, num_locs)

        # DataFrame for all the output.
        output_df = pd.DataFrame(columns=['(R, Z)', 'Psin', data], index=np.arange(0, num_locs))

        # If we want the Mach number (or speed), we need to do a little data
        # preprocessing first to see if the additional T13 drift option was on.
        if data in ['Mach', 'Velocity']:

            # Get the 2D data from the netCDF file.
            scaling  = 1.0 / self.qtim
            kvhs     = self.nc['KVHS'][:] * scaling

            # Array to hold data with T13 data added on (will be same as
            # kvhs if T13 was off).
            kvhs_adj = kvhs

            # See if T13 was on and additional values need to be added.
            try:
                pol_opt = float(self.dat_file.split('POL DRIFT OPT')[1].split(':')[0])
                if pol_opt == 0.0:
                    print('Poloidal drift option T13 was OFF.')

                elif pol_opt == 1.0:
                    print('Poloidal drift option T13 was ON.')

                    # Get the relevant table for the extra drifts out of the .dat file.
                    add_data = self.dat_file.split('TABLE OF DRIFT REGION BY RING - RINGS ' + \
                                                    'WITHOUT FLOW ARE NOT LISTED\n')[1]. \
                                                    split('DRIFT')[0].split('\n')

                    # Split the data between the spaces, put into DataFrame.
                    add_data = [line.split() for line in add_data]
                    add_df = pd.DataFrame(add_data[1:-1], columns=['IR', 'Vdrift (m/s)',
                                          'S_START (m)', 'S_END (m)'], dtype=np.float64). \
                                          set_index('IR')

                    # Loop through the KVHS data one cell at a time, and if
                    # the cell nas extra Mach flow, add it.
                    for ir in range(self.nrs):
                        for ik in range(self.nks[ir]):
                            if self.area[ir, ik] != 0.0:

                                # If this ring has additional drifts to be added.
                                if ir in add_df.index:

                                    # Then add the drift along the appropriate s (or knot) range.
                                    if self.kss[ir][ik] > add_df['S_START (m)'].loc[ir] and \
                                       self.kss[ir][ik] < add_df['S_END (m)'].loc[ir]:

                                       kvhs_adj[ir][ik] = kvhs[ir][ik] + add_df['Vdrift (m/s)'].loc[ir]

            except AttributeError:
                print("Error: .dat file has not been loaded.")
            except IndexError:
                print("Warning: Can't add on T13 flag if DIVIMP is not run.")

            # Fill in the psin values for the dataframe.
            for i in range(0, len(rs)):
                ring, knot = self.find_ring_knot(rs[i], zs[i])
                psin = self.nc['PSIFL'][:][ring][knot]
                output_df.iloc[i]['Psin'] = psin

        for i in range(0, num_locs):

            # Get the cell that has the data at this R, Z.
            ring, knot = self.find_ring_knot(rs[i], zs[i])

            if data == 'Te':
                probe = self.nc['KTEBS'][:][ring][knot]
                ylabel = 'Te (eV)'

            elif data == 'ne':
                probe = self.nc['KNBS'][:][ring][knot]
                ylabel = 'ne (m-3)'

            elif data == 'Mach':
                # Need to calculate the sound speed to back out the Mach number.
                te = self.nc['KTEBS'][:][ring][knot]
                ti = self.nc['KTIBS'][:][ring][knot]
                mb = self.crmb * 931.49 * 10**6 / ((3*10**8)**2)
                cs = np.sqrt((te + ti) / mb)
                probe = kvhs_adj[ring][knot] / cs
                ylabel = 'Mach'

            elif data == 'Velocity':
                probe = kvhs_adj[ring][knot]
                ylabel = 'Velocity (m/s)'

            output_df['(R, Z)'][i] = (rs[i], zs[i])
            output_df[data][i]   = probe

        # Make a plot of the data.
        if plot is not None:

            # Get correct X and Y arrays for plotting.
            if plot in ['R', 'r']:
                x = [output_df['(R, Z)'][i][0] for i in range(0, len(output_df.index))]
                xlabel = 'R (m)'
            elif plot in ['Z', 'z']:
                x = [output_df['(R, Z)'][i][1] for i in range(0, len(output_df.index))]
                xlabel = 'Z (m)'
            elif plot in ['psin', 'Psin']:
                x = output_df['Psin'].values
                xlabel = 'Psin'
            y = output_df[data].values

            fig = plt.figure()
            ax  = fig.add_subplot(111)
            ax.plot(x, y, lw=5, color='k')
            ax.set_xlabel(xlabel, fontsize=fontsize)
            ax.set_ylabel(ylabel, fontsize=fontsize)
            ax.tick_params(axis='both', labelsize=fontsize*0.75)

            # Set correct limit on X axis.
            #if plot == 'Z':
            #    ax.set_xlim([r_start, r_end])
            #elif plot == 'R':
            #    ax.set_xlim([z_start, z_end])

            fig.show()

        return output_df

    def along_ring(self, ring, dataname, ylabel=None, charge=None, vz_mult=0.0, plot_it=True):
        """
        Plot data along a specified ring. Will return the x, y data just in case
        you want it.

        ring:     The ring number to plot data for.
        dataname: The NetCDF variable you want the dat along the ring for. Special
                  options include 'Mach' or 'Velocity' that can add on the additional
                  drift option T13 if it was on.
        """

        # Get the parallel to B coordinate. Not sure why this "1" is needed, but
        # these is a like extra point in this KSB data to be ignored for the test
        # cases I work with.
        x = self.nc['KSB'][:][ring][1:].data

        # If we want the Mach number (or speed), we need to do a little data
        # preprocessing first to see if the additional T13 drift option was on.
        if dataname in ['Mach', 'Velocity']:

            # Get the 2D data from the netCDF file.
            scaling  = 1.0 / self.qtim
            kvhs     = self.nc['KVHS'][:] * scaling

            # Array to hold data with T13 data added on (will be same as
            # kvhs if T13 was off).
            kvhs_adj = kvhs

            try:
                pol_opt = float(self.dat_file.split('POL DRIFT OPT')[1].split(':')[0])
                if pol_opt == 0.0:
                    print('Poloidal drift option T13 was OFF.')

                elif pol_opt == 1.0:
                    print('Poloidal drift option T13 was ON.')

                    # Get the relevant table for the extra drifts out of the .dat file.
                    add_data = self.dat_file.split('TABLE OF DRIFT REGION BY RING - RINGS ' + \
                                                    'WITHOUT FLOW ARE NOT LISTED\n')[1]. \
                                                    split('DRIFT')[0].split('\n')

                    # Split the data between the spaces, put into DataFrame.
                    add_data = [line.split() for line in add_data]
                    add_df = pd.DataFrame(add_data[1:-1], columns=['IR', 'Vdrift (m/s)',
                                          'S_START (m)', 'S_END (m)'], dtype=np.float64). \
                                          set_index('IR')

                    # Loop through the KVHS data one cell at a time, and if
                    # the cell nas extra Mach flow, add it.
                    for ir in range(self.nrs):
                        for ik in range(self.nks[ir]):
                            if self.area[ir, ik] != 0.0:

                                # If this ring has additional drifts to be added.
                                if ir in add_df.index:

                                    # Then add the drift along the appropriate s (or knot) range.
                                    if self.kss[ir][ik] > add_df['S_START (m)'].loc[ir] and \
                                       self.kss[ir][ik] < add_df['S_END (m)'].loc[ir]:

                                       kvhs_adj[ir][ik] = kvhs[ir][ik] + add_df['Vdrift (m/s)'].loc[ir]

            except AttributeError:
                print("Error: .dat file has not been loaded.")

            # Finally put it into the y value of the ring we want.
            if dataname == 'Mach':

                # Need to calculate the sound speed to back out the Mach number.
                te = self.nc['KTEBS'][:][ring]
                ti = self.nc['KTIBS'][:][ring]
                mb = self.crmb * 931.49 * 10**6 / ((3*10**8)**2)
                cs = np.sqrt((te + ti) / mb)
                y  = kvhs_adj[ring] / cs
                #ylabel = 'Mach'

            elif dataname == 'Velocity':
                y  = kvhs_adj[ring]
                #ylabel = 'Velocity (m/s)'

        # If you want the impurity density, make sure you can handle the sum
        # across all the charge states or a specific charge state.
        elif dataname =='DDLIMS':
            scaling = self.absfac
            if charge == 'all':
                y = self.nc[dataname][:].sum(axis=0)[ring] * scaling
            else:
                y = self.nc[dataname][:][charge][ring] * scaling

        # Pull from the forces data if you want a force plot.
        elif dataname.lower() in ['ff', 'fig', 'feg', 'fpg', 'fe', 'fnet', 'ff']:

            # Some constants and required factors.
            col_log = 15
            qe      = 1.602E-19
            amu_kg  = 1.66E-27
            fact = np.power(self.qtim, 2) * qe / amu_kg

            if dataname.lower() == 'fig':

                # Need charge to calculate FiG.
                if charge == None:
                    print("Error: Must supply a charge state to calculate FiG")
                    return None

                mu = self.crmi / (self.crmi + self.crmb)
                beta = 3 * (mu + 5 * np.sqrt(2) * np.power(charge, 2) * \
                       (1.1 * np.power(mu, 5/2)- 0.35 * np.power(mu, 3/2)) - 1) / \
                       (2.6 - 2 * mu + 5.4 * np.power(mu, 2))
                print("FiG: Beta = {:.2f}".format(beta))

                # Again, must scale the gradient with this scaling factor.
                #kfigs = self.read_data_2d('KFIGS', scaling = qe / fact)

                kfigs = self.nc['KFIGS'][:][ring].data * qe / fact

                # Calculate the force.
                fig = beta * kfigs
                y = fig

            elif dataname.lower() == 'ff':

                # Need charge to calculate FF.
                if charge == None:
                    print("Error: Must supply a charge sate to calculate FiG")
                    return None

                ti = self.nc['KTIBS'][:][ring]
                ne = self.nc['KNBS'][:][ring]

                # Slowing down time.
                tau_s = 1.47E13 * self.crmi * ti * np.sqrt(ti / self.crmb) / \
                        ((1 + self.crmb / self.crmi) * ne * np.power(charge, 2) * col_log)

                # TODO: Currently will assume impurity velocity is some fraction of the
                # background velocity (default zero), though this is obviously not true
                # and a better implementation would use the real values wherever they are.

                # Don't forget KVHS is scaled by 1/QTIM to get m/s.
                scaling = 1.0 / self.qtim
                #vi = self.read_data_2d('KVHS', scaling=scaling)
                vi = self.nc['KVHS'][:][ring].data * scaling

                vz = vz_mult * vi

                # Calculate the force.
                ff = self.crmi * amu_kg * (vi - vz) / tau_s
                y = ff

            elif dataname.lower() == 'fe':

                # This also gets scaled by a factor as well in Jake's code.
                #e_pol = self.read_data_2d('E_POL', scaling = qe / fact
                e_pol = self.nc['E_POL'][:][ring].data * qe / fact
                fe = charge * qe * e_pol
                y = fe

            elif dataname.lower() == 'feg':

                alpha = 0.71 * np.power(charge, 2)

                # The electron temperature gradient from the code. I don't understand
                # this scaling factor, but Jake uses it to get into presumably eV/m.
                #kfegs = self.read_data_2d('KFEGS', scaling = qe / fact)
                kfegs = self.nc['KFEGS'][:][ring] * qe / fact

                # Calculate the force.
                feg = alpha * kfegs
                y = feg

            elif dataname.lower() == 'fpg':

                # Parallel collisional diffusion time.
                tau_par = 1.47E13 * self.crmi * ti * np.sqrt(ti / self.crmb) / \
                          (ne * np.power(charge, 2) * col_log)

                print("Error: FPG not implemented")
                return None


        else:
            # Get the data for this ring.
            y = self.nc[dataname][:][ring].data

        # Remove any (0, 0) data points that may occur due to fortran being fortran.
        drop_idx = np.array([])
        for i in range(0, len(x)):
             if x[i] == 0.0 and y[i] == 0.0:
                 drop_idx = np.append(drop_idx, i)

        x = np.delete(x, drop_idx)
        y = np.delete(y, drop_idx)

        if plot_it:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.plot(x, y, 'k-')
            ax.set_xlabel('S (m)', fontsize=18)
            ax.set_ylabel(ylabel, fontsize=18)
            ax.tick_params(axis='both', labelsize=18*0.75)
            fig.tight_layout()
            fig.show()

        return x, y
