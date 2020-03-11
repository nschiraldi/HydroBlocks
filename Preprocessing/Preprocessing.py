import warnings
warnings.filterwarnings('ignore')
import sys
sys.path.append('Tools')
#import cPickle as pickle
import pickle
import datetime
#import gdal_tools
import numpy as np
import scipy.sparse as sparse
import scipy.stats as stats
import model_tools as mt
import os
import netCDF4 as nc
import time
import glob
from geospatialtools import gdal_tools
#from geospatialtools import terrain_tools
import terrain_tools as terrain_tools
#import matplotlib.pyplot as plt
#import random
import gc
from scipy.interpolate import griddata

dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append('%s/../HydroBlocks/pyHWU/' % dir )
import management_funcs as mgmt_funcs

def plot_data(data):

 import matplotlib.pyplot as plt
 data = np.ma.masked_array(data,data==-9999)
 plt.figure(figsize=(10,10))
 #plt.imshow(data,cmap=plt.get_cmap('Paired'))
 plt.imshow(data)
 plt.colorbar()
 plt.savefig('tmp.png')

 return


def Prepare_Model_Input_Data(hydroblocks_info):

 #Prepare the info dictionary
 info = {}

 #Define the start/end dates
 info['time_info'] = {}
 info['time_info']['startdate'] = hydroblocks_info['idate']
 info['time_info']['enddate'] = hydroblocks_info['fdate']
 info['time_info']['dt'] = hydroblocks_info['dt']

 #Define the workspace
 workspace = hydroblocks_info['workspace']

 #Define the model input data directory
 input_dir = workspace#'%s/input' % workspace

 #Read in the metadata
 #file = '%s/workspace_info.pck' % workspace
 #wbd = pickle.load(open(file))

 #Create the dictionary to hold all of the data
 output = {}

 #Create the Latin Hypercube (Clustering)
 nhru = hydroblocks_info['nhru']
 #ncores = hydroblocks_info['ncores']
 icatch = hydroblocks_info['icatch']

 #Get metadata
 md = gdal_tools.retrieve_metadata('%s/mask_latlon.tif' % workspace)
 
 #Prepare the input file
 wbd = {}
 wbd['bbox'] = {'minlat':md['miny'],'maxlat':md['maxy'],
                'minlon':md['minx'],'maxlon':md['maxx'],
                'res':abs(md['resx'])}

 wbd['files'] = {
  'WLTSMC':'%s/theta1500_ea.tif' % workspace,
  'TEXTURE_CLASS':'%s/texture_class_ea.tif' % workspace,
  'cslope':'%s/cslope_ea.tif' % workspace,
  'MAXSMC':'%s/thetas_ea.tif' % workspace,
  'BB':'%s/bb_ea.tif' % workspace,
  'DRYSMC':'%s/thetar_ea.tif' % workspace,
  'fdir':'%s/fdir_ea.tif' % workspace,
  'QTZ':'%s/qtz_ea.tif' % workspace,
  'SATDW':'%s/dsat_ea.tif' % workspace,
  'REFSMC':'%s/theta33_ea.tif' % workspace,
  'mask':'%s/mask_ea.tif' % workspace,
  'SATPSI':'%s/psisat_ea.tif' % workspace,
  'lc':'%s/lc_ea.tif' % workspace,
  'carea':'%s/carea_ea.tif' % workspace,
  'ti':'%s/ti_ea.tif' % workspace,
  'ndvi':'%s/ndvi_ea.tif' % workspace,
  'F11':'%s/f11_ea.tif' % workspace,
  'SATDK':'%s/ksat_ea.tif' % workspace,
  'dem':'%s/dem_ea.tif' % workspace,
  'demns':'%s/demns_ea.tif' % workspace,
  'sand':'%s/sand_ea.tif' % workspace,
  'clay':'%s/clay_ea.tif' % workspace,
  'silt':'%s/silt_ea.tif' % workspace,
  'om':'%s/om_ea.tif' % workspace,
  'bare30':'%s/bare30_ea.tif' % workspace,
  'water30':'%s/water30_ea.tif' % workspace,
  'tree30':'%s/tree30_ea.tif' % workspace,
  'irrig_land':'%s/irrig_land_ea.tif' % workspace,
  'dbedrock':'%s/dbedrock_ea.tif' % workspace
  }
 if hydroblocks_info['water_management']['hwu_agric_flag']:
   wbd['files']['irrig_land'] = '%s/irrig_land_ea.tif' % workspace
   wbd['files']['start_growing_season'] = '%s/start_growing_season_ea.tif' % workspace
   wbd['files']['end_growing_season']   = '%s/end_growing_season_ea.tif' % workspace

 wbd['files_meteorology'] = {
  'lwdown':'%s/lwdown.nc' % workspace,
  'swdown':'%s/swdown.nc' % workspace,
  'tair':'%s/tair.nc' % workspace,
  'precip':'%s/precip.nc' % workspace,
  'psurf':'%s/psurf.nc' % workspace,
  'wind':'%s/wind.nc' % workspace,
  'spfh':'%s/spfh.nc' % workspace,
  }

 if hydroblocks_info['water_management']['hwu_flag'] == True:
  wbd['files_water_use'] = {}
  if hydroblocks_info['water_management']['hwu_domest_flag']:
   wbd['files_water_use']['domestic']   = '%s/domestic.nc' % workspace
  if hydroblocks_info['water_management']['hwu_indust_flag']:
   wbd['files_water_use']['industrial'] = '%s/industrial.nc' % workspace
  if hydroblocks_info['water_management']['hwu_lstock_flag']:
   wbd['files_water_use']['livestock']  = '%s/livestock.nc' % workspace
  

 #Create the clusters and their connections
 output = Create_Clusters_And_Connections(workspace,wbd,output,input_dir,nhru,info,hydroblocks_info)

 #Extract the meteorological forcing
 print("Preparing the meteorology")
 if hydroblocks_info['model_type'] == 'semi':
  Prepare_Meteorology_Semidistributed(workspace,wbd,output,input_dir,info,hydroblocks_info)
 elif hydroblocks_info['model_type'] == 'full':
  Prepare_Meteorology_Fulldistributed(workspace,wbd,output,input_dir,info,hydroblocks_info)

 #Extract the water use demands
 print("Preparing the water use")
 if hydroblocks_info['model_type'] == 'semi':
  if hydroblocks_info['water_management']['hwu_flag'] == True:
   Prepare_Water_Use_Semidistributed(workspace,wbd,output,input_dir,info,hydroblocks_info) 
 elif hydroblocks_info['model_type'] == 'full':
   exit('Error: Human Water Management not implemented in the fully distributed mode yet.')

 #Write out the files to the netcdf file
 fp = hydroblocks_info['input_fp']
 data = output

 #Write out the metadata
 grp = fp.createGroup('metadata')
 grp.latitude = (wbd['bbox']['minlat'] + wbd['bbox']['maxlat'])/2
 lon = (wbd['bbox']['minlon'] + wbd['bbox']['maxlon'])/2 
 if lon < 0:lon += 360
 grp.longitude = lon
 metadata = gdal_tools.retrieve_metadata(wbd['files']['mask']) 
 grp.dx = metadata['resx']
 #grp.longitude = (360.0+(wbd['bbox']['minlon'] + wbd['bbox']['maxlon'])/2)

 #Write the HRU mapping
 #CONUS conus_albers metadata
 metadata['nodata'] = -9999.0
 #Save the conus_albers metadata
 grp = fp.createGroup('conus_albers_mapping')
 grp.createDimension('nx',metadata['nx'])
 grp.createDimension('ny',metadata['ny'])
 hmca = grp.createVariable('hmca','f4',('ny','nx'))#,zlib=True) 
 hmca.gt = metadata['gt']
 hmca.projection = metadata['projection']
 hmca.description = 'HSU mapping (conus albers)'
 hmca.nodata = metadata['nodata']
 #Save the conus albers mapping
 hsu_map = np.copy(output['hsu_map'])
 hsu_map[np.isnan(hsu_map) == 1] = metadata['nodata']
 hmca[:] = hsu_map

 #Write out the mapping
 file_ca = '%s/hsu_mapping_ea.tif' % workspace
 gdal_tools.write_raster(file_ca,metadata,hsu_map)

 #Map the mapping to regular lat/lon
 file_ll = '%s/hsu_mapping_latlon.tif' % workspace
 os.system('rm -f %s' % file_ll)
 res = wbd['bbox']['res']
 minlat = wbd['bbox']['minlat']
 minlon = wbd['bbox']['minlon']
 maxlat = wbd['bbox']['maxlat']
 maxlon = wbd['bbox']['maxlon']
 log = '%s/log.txt' % workspace
 lon_0 = (maxlon+minlon)/2.0
 lat_0 = (maxlat+minlat)/2.0
 os.system('gdalwarp -tr %f %f -dstnodata %f -r mode -t_srs \'+proj=longlat +lon_0=%f +lat_0=%f +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +no_defs \' -te %.16f %.16f %.16f %.16f %s %s >> %s 2>&1' % (res,res,metadata['nodata'],lon_0,lat_0,minlon,minlat,maxlon,maxlat,file_ca,file_ll,log))

 #Write a map for the catchment id
 file_icatch = '%s/icatch_latlon.tif' % workspace
 metadata = gdal_tools.retrieve_metadata(file_ll)
 metadata['nodata'] = -9999.0
 tmp = gdal_tools.read_raster(file_ll)
 tmp[tmp >= 0] = hydroblocks_info['icatch']
 gdal_tools.write_raster(file_icatch,metadata,tmp)
 

 #Retrieve the lat/lon metadata
 #metadata = gdal_tools.retrieve_metadata(file_ll)
 #metadata['nodata'] = -9999.0
 #Save the lat/lon metadata
 #grp = fp.createGroup('latlon_mapping')
 #grp.createDimension('nlon',metadata['nx'])
 #grp.createDimension('nlat',metadata['ny'])
 #hmll = grp.createVariable('hmll','f4',('nlat','nlon'))
 #hmll.gt = metadata['gt']
 #hmll.projection = metadata['projection']
 #hmll.description = 'HSU mapping (regular lat/lon)'
 #hmll.nodata = metadata['nodata']
 #Save the lat/lon mapping
 #hsu_map = np.copy(gdal_tools.read_raster(file_ll))
 #hsu_map[np.isnan(hsu_map) == 1] = metadata['nodata']
 #hmll[:] = hsu_map

 #Write the flow matrix
 flow_matrix = output['flow_matrix']
 nconnections = flow_matrix.data.size
 grp = fp.createGroup('flow_matrix')
 grp.createDimension('connections_columns',flow_matrix.indices.size)
 grp.createDimension('connections_rows',flow_matrix.indptr.size)
 grp.createVariable('data','f4',('connections_columns',))
 grp.createVariable('indices','f4',('connections_columns',))
 grp.createVariable('indptr','f4',('connections_rows',))
 grp.variables['data'][:] = flow_matrix.data
 grp.variables['indices'][:] = flow_matrix.indices
 grp.variables['indptr'][:] = flow_matrix.indptr

 #Write the connection matrices
 #width
 wmatrix = output['cmatrix']['width']
 nconnections = wmatrix.data.size
 grp = fp.createGroup('wmatrix')
 grp.createDimension('connections_columns',wmatrix.indices.size)
 grp.createDimension('connections_rows',wmatrix.indptr.size)
 grp.createVariable('data','f4',('connections_columns',))
 grp.createVariable('indices','f4',('connections_columns',))
 grp.createVariable('indptr','f4',('connections_rows',))
 grp.variables['data'][:] = wmatrix.data
 grp.variables['indices'][:] = wmatrix.indices
 grp.variables['indptr'][:] = wmatrix.indptr

 #Write the outlet information
 outlet = output['outlet']
 grp = fp.createGroup('outlet')
 full = grp.createGroup('full')
 full.createDimension('cell',outlet['full']['hru_org'].size)
 full.createVariable('i','i4',('cell',))
 full.createVariable('j','i4',('cell',))
 full.createVariable('hru_org','i4',('cell',))
 full.createVariable('hru_dst','i4',('cell',))
 full.createVariable('d8','i4',('cell',))
 full.variables['i'][:] = outlet['full']['i']
 full.variables['j'][:] = outlet['full']['j']
 full.variables['hru_org'][:] = outlet['full']['hru_org']
 full.variables['hru_dst'][:] = outlet['full']['hru_dst']
 full.variables['d8'][:] = outlet['full']['d8']
 summary = grp.createGroup('summary')
 summary.createDimension('hru',outlet['summary']['hru_org'].size)
 summary.createVariable('hru_org','i4',('hru',))
 summary.createVariable('hru_dst','i4',('hru',))
 summary.createVariable('counts','i4',('hru',))
 summary.variables['hru_org'][:] = outlet['summary']['hru_org']
 summary.variables['hru_dst'][:] = outlet['summary']['hru_dst']
 summary.variables['counts'][:] = outlet['summary']['counts']
 #outlet = {'full':{'i':outlet_icoord,'j':outlet_jcoord,'hru_org':outlet_hru_org,'hru_dst':outlet_hru_dst,'d8':outlet_d8},
 #          'summary':{'hru_org':outlet_hru_org_summary,'hru_dst':outlet_hru_dst_summary,'counts':counts}}

 #Write the model parameters
 grp = fp.createGroup('parameters')
 vars = ['slope','area_pct','land_cover','channel',
        'dem','soil_texture_class','ti','carea','area',
        'BB','F11','SATPSI','SATDW','QTZ','clay',
        'WLTSMC','MAXSMC','DRYSMC','REFSMC','SATDK',
        'mannings','m','psoil','pksat','sdmax','hand']

 if hydroblocks_info['water_management']['hwu_agric_flag']:
  for var in ['centroid_lats', 'centroid_lons', 'irrig_land', 'start_growing_season', 'end_growing_season']:
    vars.append(var)

 for var in vars:
  grp.createVariable(var,'f4',('hsu',))#,zlib=True)
  grp.variables[var][:] = data['hsu'][var]

 if hydroblocks_info['water_management']['hwu_flag']:
  grp.createVariable('hru_min_dist','f4',('hsu','hsu'))#,zlib=True)
  grp.variables['hru_min_dist'][:] = data['hsu']['hru_min_dist']


 #Write other metadata
 #grp = fp.createGroup('metadata')
 #grp.outlet_hsu = data['outlet']['hsu']

 #Remove info from output
 del output['hsu']

 #Add in the catchment info
 output['wbd'] = wbd

 #Close the file
 fp.close()

 return output

def Compute_HRUs_Fulldistributed(covariates,mask,nhru):

 cluster_ids = np.empty(covariates['ti'].shape)
 cluster_ids[:] = -9999
 cluster_ids[mask == True] = np.arange(nhru)

 return (cluster_ids,)

def Compute_HRUs_Semidistributed_Kmeans(covariates,mask,nhru,hydroblocks_info,wbd):

 #Define the number of requested hrus (channel and non-channel)
 nhru = hydroblocks_info['nhru']
 
 #Find the mask for and without channels
 mask_nc = mask
 
 #Mask regions without soil properties
 tmp_clay = gdal_tools.read_raster(wbd['files']['clay'])
 tmp_lc = gdal_tools.read_raster(wbd['files']['lc'])
 nodata = (tmp_clay == -9999) & ((tmp_lc == 17) | (tmp_lc == -9999))
 mask_nc[nodata]=False
 del tmp_clay,tmp_lc
 gc.collect()

 
 #Define the covariates
 info_general = {}
 for var in covariates:
   if var == 'carea':    info_general['area'] =  {'data':np.log(covariates['carea'][mask_nc == True]),}
   elif var == 'cslope': info_general['slope'] = {'data':covariates['cslope'][mask_nc == True],}
   elif var == 'SATDK':  info_general['ksat'] =  {'data':covariates['SATDK'][mask_nc == True],}
   elif var == 'BB':     info_general['bc_b'] =  {'data':covariates['BB'][mask_nc == True],}
   elif var == 'SATPSI': info_general['bc_psisat'] = {'data':covariates['SATPSI'][mask_nc == True],}
   elif var == 'MAXSMC': info_general['sms'] =   {'data':covariates['MAXSMC'][mask == True],}
   elif var == 'WLTSMC': info_general['smw'] =   {'data':covariates['WLTSMC'][mask == True],}
   else: info_general[var] =   {'data':covariates[var][mask == True],}


 #Subset the chosen ones for the non-channels
 info = {}
 for var in hydroblocks_info['covariates']:
  info[var] = info_general[var]

 #Scale all the variables (Calculate the percentiles
 for var in info:
  #print var, info[var]['data'], np.nanmax(info[var]['data']), np.nanmin(info[var]['data']), np.nanmean(info[var]['data'])
  #if var in ['clay','ndvi','ti','lats','lons']:
  if hydroblocks_info['covariates'][var] == 'p':
   #print hydroblocks_info['covariates'][var] 
   argsort = np.argsort(info[var]['data'])
   pcts = np.copy(info[var]['data'])
   pcts[argsort] = np.linspace(0,1,len(info[var]['data']))
   uniques,counts = np.unique(info[var]['data'],return_counts=True)
   for ival in range(uniques.size):
    value = uniques[ival]
    count = counts[ival]
    if count <= 10:continue
    pcts[info[var]['data'] == value] = np.nanmean(pcts[info[var]['data'] == value])
   info[var]['data'][:] = pcts[:]
  else:
   tmp = info[var]['data']
   utmp = np.unique(tmp)
   utmp = utmp[utmp != -9999.0]
   if len(utmp) > 1:
    tmp = (tmp - np.nanmin(tmp))/(np.nanmax(tmp) - np.nanmin(tmp))
    info[var]['data'] = tmp
   else:
    tmp[tmp != -9999.0] = 0.5
    info[var]['data'] = tmp



 import sklearn.cluster
 #Cluster the non channels regions
 bins,data = [],[]
 X = []
 for id in info:
  #Set all nans to the mean
  
  # Noemi addition
  if np.isnan(np.nanmean(info[id]['data'])) == 1:
    print("ERROR: all values for clustering are Nan, catch:",hydroblocks_info['icatch'],id, info[id]['data'])
    info[id]['data'][:] = 0.5

  info[id]['data'][np.isnan(info[id]['data']) == 1] = np.nanmean(info[id]['data'])
  X.append(info[id]['data'])


 time0 = time.time()
 X = np.array(X).T
 #Subsample the array
 np.random.seed(123)
 #minsamples = 3*10**5
 minsamples = X.shape[0] #Noemi
 if X.shape[0] > minsamples:
  Xf = X[np.random.choice(np.arange(X.shape[0]),minsamples),:]
 else:
  Xf = X

 #Initialize all points at the 0.5 point
 if nhru > len(info[id]['data'])/10:
   nhru=int(len(info[id]['data'])/10)  # Noemi
 init = 0.5*np.ones((nhru,Xf.shape[1]))
 batch_size = 25*nhru
 init_size = 3*batch_size
 clf = sklearn.cluster.MiniBatchKMeans(nhru,random_state=1,init=init,batch_size=batch_size,init_size=init_size)
 clf.fit(Xf)#
 clf_output = clf.predict(X)

 #Reassign the ids
 clf_output_copy = np.copy(clf_output)
 for cid in range(len(np.unique(clf_output))):
  clf_output[clf_output_copy == np.unique(clf_output)[cid]] = cid
 cluster_ids = np.empty(covariates['ti'].shape)
 cluster_ids[:] = -9999
 cluster_ids[mask_nc == True] = clf_output
 nhru_old = nhru
 nhru = np.unique(cluster_ids).size-1

 #Redefine the number of clusters (We are sampling regions that just don't have data...)
 print('clustering %d->%d' % (nhru_old,nhru),time.time() - time0)

 #Reorder according to areas
 areas = []
 for cid in range(nhru):
  msk = cluster_ids == cid
  #areas.append(np.nanmean(covariates['carea'][msk]))
  areas.append(np.nanmax(covariates['carea'][msk]))
 argsort = np.argsort(np.array(areas))
 cluster_ids_new = np.copy(cluster_ids)
 for cid in range(nhru):
  msk = cluster_ids == argsort[cid]
  cluster_ids_new[msk] = cid
 cluster_ids = np.copy(cluster_ids_new)
 areas = []
 for cid in range(nhru):
  msk = cluster_ids == cid
  areas.append(np.nanmean(covariates['carea'][msk]))

 return (cluster_ids,nhru)

def Compute_HRUs_Semidistributed_HMC(covariates,mask,hydroblocks_info,wbd,eares):

 #PARAMETERS (NEED TO GO OUTSIDE)
 #eares = 30 #meters

 #Define the parameters for the hierarchical multivariate clustering
 ncatchments = hydroblocks_info['hmc_parameters']['number_of_characteristic_subbasins']
 dh = hydroblocks_info['hmc_parameters']['average_height_difference_between_bands']
 nclusters = hydroblocks_info['hmc_parameters']['number_of_intraband_clusters']

 #Pre-process DEM
 dem = covariates['dem']
 #Remove pits in dem
 print("Removing pits in dem")
 demns = terrain_tools.ttf.remove_pits_planchon(dem,eares)
 covariates['demns'] = demns
  
 #Calculate slope and aspect
 print("Calculating slope and aspect")
 res_array = np.copy(demns)
 res_array[:] = eares
 (slope,aspect) = terrain_tools.ttf.calculate_slope_and_aspect(demns,res_array,res_array)

 #Compute accumulated area
 m2 = np.copy(demns)
 m2[:] = 1
 print("Calculating accumulated area")
 (area,fdir) = terrain_tools.ttf.calculate_d8_acc(demns,m2,eares)

 #Calculate channel initiation points (2 parameters)
 C = area/eares*slope**2
 ipoints = ((C > 200) & (area > 10**5)).astype(np.int32)
 ipoints[ipoints == 0] = -9999

 #Create area for channel delineation
 (ac,fdc) = terrain_tools.ttf.calculate_d8_acc_wipoints(demns,m2,ipoints,eares)
 ac[ac != 0] = area[ac != 0]

 #Compute the channels
 print("Defining channels")
 channels = terrain_tools.ttf.calculate_channels_wocean(ac,10**4,10**4,fdc,m2)
 #area_in,threshold,basin_threshold,fdir,channels,nx,ny)
 #channels = terrain_tools.ttf.calculate_channels(ac,10**4,10**4,fdc)#,m2)
 channels = np.ma.masked_array(channels,channels<=0)

 #If the dem is undefined then set to undefined
 channels[dem == -9999] = -9999

 #Compute the basins
 print("Defining basins")
 basins = terrain_tools.ttf.delineate_basins(channels,m2,fdir)
 #basins[basins != 637] = -9999
 #channels[channels != 637] = -9999
 #print(basins[670,225])
 #plot_data(channels)
 #plot_data(basins)
 #exit()

 #Calculate the height above nearest drainage area
 print("Computing height above nearest drainage area")
 hand = terrain_tools.ttf.calculate_depth2channel(channels,basins,fdir,demns)
 if np.all( (hand == -9999) ): hand[:] = 0.0 # Noemi
 
 #Calculate topographic index
 print("Computing topographic index")
 ti = np.copy(area)
 m = (area != -9999) & (slope != -9999) & (slope != 0.0)
 ti[m] = np.log(area[m]/eares/slope[m])
 ti[slope == 0] = 15.0

 #Cleanup
 '''#Mask regions without soil properties
 tmp_clay = gdal_tools.read_raster(wbd['files']['clay'])
 tmp_lc = gdal_tools.read_raster(wbd['files']['lc'])
 nodata = (tmp_clay == -9999) & ((tmp_lc == 17) | (tmp_lc == -9999))
 mask[nodata]=0
 del tmp_clay,tmp_lc
 gc.collect()
 '''

 # cleanup
 slope[mask != 1] = -9999
 aspect[mask != 1] = -9999
 area[mask != 1] = -9999
 channels[mask != 1] = -9999
 basins[mask != 1] = -9999
 #hand[mask != 1] = -9999
 ti[mask != 1] = -9999

 covariates['slope'] = slope
 covariates['aspect'] = aspect
 covariates['carea'] = area
 #covariates['fdir'] = fdir
 covariates['ti'] = ti

 '''
 import matplotlib.pyplot as plt
 plt.imshow(mask); plt.show()
 tmp = np.copy(basins).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 tmp = np.copy(hand).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 '''

 #Calculate the subbasin properties
 print("Assembling the subbasin properties")
 hp_in = terrain_tools.calculate_basin_properties_updated(basins,eares,covariates,hydroblocks_info['hmc_parameters']['subbasin_clustering_covariates'])

 #Clustering the basins
 print("Clustering the basins")
 #Assemble input data
 cvs = {}
 for var in hydroblocks_info['hmc_parameters']['subbasin_clustering_covariates']:
  tmp = np.copy(hp_in[var])
  cvs[var] = {'min':np.min(hp_in[var]),
              'max':np.max(hp_in[var]),
              't':-9999,
              'd':tmp}
 
 (basin_clusters,) = terrain_tools.cluster_basins_updated(basins,cvs,hp_in,ncatchments)
  
 # remove tiny basins clusters
 ubcs = np.unique(basin_clusters)
 ubcs = ubcs[ubcs!=-9999]
 for ubc in ubcs:
  m = basin_clusters == ubc
  valid_vals = (hand[m] != -9999) 
  #if the basin cluster has less than 50% of valid hand values
  if np.sum(valid_vals) > 0:
    missing_ratio = 1.0 - (np.sum(valid_vals)/float(np.sum(m)))  
  else:
    missing_ratio = 1.0
  if missing_ratio > 0.9 : 
    basin_clusters[m] = -9999
    basins[m] = -9999
 if len(basin_clusters[basin_clusters != -9999]) < 1 : 
  exit('Error_basin_clustering: hand_full_of_nans %s' % hydroblocks_info['icatch']) 

 '''
 print basin_clusters, basin_clusters.shape
 import matplotlib.pyplot as plt
 tmp = np.copy(covariates['lc']).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 tmp = np.copy(covariates['clay']).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 tmp = np.copy(basins).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 tmp = np.copy(basin_clusters).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 tmp = np.copy(hand).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 tmp = np.copy(hand-basin_clusters).astype(float); tmp[tmp==-9999]=np.nan
 plt.imshow(tmp); plt.show()
 '''
 
 #Divide each subbasin into height bands
 (tiles,new_hand,tile_position) = terrain_tools.create_basin_tiles(basin_clusters,hand,basins,dh)

 #Disagregate land cover
 intraband_clust_vars = hydroblocks_info['hmc_parameters']['intraband_clustering_covariates']
 #print(intraband_clust_vars)
 if 'lc' in intraband_clust_vars: 
  intraband_clust_vars.remove('lc')
  disag = [i for i in covariates.keys() if 'lc_' in i]
  intraband_clust_vars = intraband_clust_vars + disag
  #print(intraband_clust_vars)

 #Calculate the hrus (kmeans on each tile of each basin)
 cvs = {}
 for var in intraband_clust_vars:
  cvs[var] = {'min':np.min(covariates[var][covariates[var]!=-9999]),
              'max':np.max(covariates[var][covariates[var]!=-9999]),
              't':-9999,
              'd':covariates[var]}
 #print("Clustering the height bands into %d clusters" % nclusters)
 hrus = terrain_tools.create_hrus_hydroblocks(basin_clusters,tiles,cvs,nclusters)
 hrus[hrus!=-9999] = hrus[hrus!=-9999] - 1
 nhru = np.unique(hrus[hrus!=-9999]).size
 
 #plot
 #print nhru
 #plot_data(hrus)

 #Construct HMC info for creating connections matrix
 HMC_info = {}
 HMC_info['basins'] = basins
 HMC_info['tile_position'] = tile_position

 return (hrus.astype(np.float32),nhru,new_hand,HMC_info,covariates)

def Assign_Parameters_Fulldistributed(covariates,metadata,hydroblocks_info,OUTPUT,cluster_ids,mask):

 nhru = hydroblocks_info['nhru']
 #Initialize the arrays
 vars = ['area','area_pct','BB','DRYSMC','F11','MAXSMC','REFSMC','SATPSI',
         'SATDK','SATDW','WLTSMC','QTZ','slope','ti','dem','carea','channel',
         'land_cover','soil_texture_class']
 #vars = ['area','area_pct','BB','DRYSMC','F11','MAXSMC','REFSMC','SATPSI',
 #        'SATDK','SATDW','WLTSMC','QTZ','slope','ti','dem','carea','channel',         'vchan','vof','land_cover','soil_texture_class']
 OUTPUT['hsu'] = {}
 for var in vars:
  OUTPUT['hsu'][var] = np.zeros(nhru) 

 #Calculate area per hsu
 OUTPUT['hsu']['area'][:] = metadata['resx']**2
 #Calculate area percentage per hsu
 OUTPUT['hsu']['area_pct'][:] = 100*OUTPUT['hsu']['area']/(metadata['resx']**2*nhru)
 #Soil properties
 for var in ['BB','DRYSMC','F11','MAXSMC','REFSMC','SATPSI','SATDK','SATDW','WLTSMC','QTZ']:
  if var in ['SATDK','SATDW']:
   OUTPUT['hsu'][var][:] = covariates[var][mask]
  else:
   OUTPUT['hsu'][var][:] = covariates[var][mask]
 #Average Slope
 OUTPUT['hsu']['slope'][:] = covariates['cslope'][mask]
 #Topographic index
 OUTPUT['hsu']['ti'][:] = covariates['ti'][mask]
 #DEM
 OUTPUT['hsu']['dem'][:] = covariates['dem'][mask]
 #HAND
 OUTPUT['hsu']['hand'][:] = covariates['hand'][mask]
 #Average Catchment Area
 OUTPUT['hsu']['carea'][:] = covariates['carea'][mask]
 #Channel?
 OUTPUT['hsu']['channel'][:] = covariates['channels'][mask]
 #Land cover type  
 land_cover = np.copy(covariates['nlcd'])
 #for lc in np.unique(land_cover)[1:]:
 # land_cover[land_cover == lc] = NLCD2NOAH[lc]
 OUTPUT['hsu']['land_cover'][:] = land_cover[mask]
 #Soil texture class
 OUTPUT['hsu']['soil_texture_class'][:] = covariates['TEXTURE_CLASS'][mask]
 #Define the estimate for the model parameters
 OUTPUT['hsu']['m'][:] = covariates['dbedrock'][mask] #Form of the exponential decline in conductivity (0.01-1.0)
 OUTPUT['hsu']['pksat'][:] = 1.0 #saturated hydraulic conductivity scalar multiplier (0.1-1.0)
 OUTPUT['hsu']['psoil'][:] = 1.0 #soil hydraulic properties (residual,wilting,field capacity, and porosity) (0.1-10.0)
 OUTPUT['hsu']['sdmax'][:] = 5.0 #maximum effective deficit of subsurface saturated zone (0.1-10.0)
 OUTPUT['hsu']['mannings'][covariates['carea'][mask] >= 100000.0] = 0.03 #manning's n for channel flow (0.01-0.1)
 OUTPUT['hsu']['mannings'][covariates['carea'][mask] < 100000.0] = 0.15 #manning's n for overland flow (0.01-0.8)

 return OUTPUT

def Assign_Parameters_Semidistributed(covariates,metadata,hydroblocks_info,OUTPUT,cluster_ids,mask):

 nhru = hydroblocks_info['nhru']
 #Initialize the arrays
 vars = ['area','area_pct','BB','DRYSMC','F11','MAXSMC','REFSMC','SATPSI',
         'SATDK','SATDW','WLTSMC','QTZ','slope','ti','dem','carea','channel',
         'land_cover','soil_texture_class','clay','sand','silt',
         'mannings','m','psoil','pksat','sdmax','hand']

 if hydroblocks_info['water_management']['hwu_agric_flag']:
  for var in ['centroid_lats', 'centroid_lons', 'irrig_land', 'start_growing_season', 'end_growing_season']:
    vars.append(var)

 OUTPUT['hsu'] = {}
 if hydroblocks_info['water_management']['hwu_flag']: OUTPUT['hsu']['hru_min_dist'] = np.zeros((nhru,nhru))
 for var in vars:
   OUTPUT['hsu'][var] = np.zeros(nhru)


 #Metadata
 for hsu in np.arange(nhru):
  #Set indices
  idx = np.where(cluster_ids == hsu)
  #Calculate area per hsu
  OUTPUT['hsu']['area'][hsu] = metadata['resx']**2*idx[0].size
  #Calculate area percentage per hsu
  OUTPUT['hsu']['area_pct'][hsu] = 100*OUTPUT['hsu']['area'][hsu]/(metadata['resx']**2*mask[mask].size)
  #Soil properties
  for var in ['BB','DRYSMC','F11','MAXSMC','REFSMC','SATPSI','SATDK','SATDW','WLTSMC','QTZ','clay','sand','silt']:
   if var in ['SATDK','SATDW']:
    OUTPUT['hsu'][var][hsu] = stats.mstats.hmean(covariates[var][idx])/3600.0/1000.0 #mm/hr -> m/s
   else:
    #OUTPUT['hsu'][var][hsu] = stats.mstats.gmean(covariates[var][idx])
    OUTPUT['hsu'][var][hsu] = np.mean(covariates[var][idx])
  #Average Slope
  OUTPUT['hsu']['slope'][hsu] = np.nanmean(covariates['slope'][idx])
  #Topographic index
  OUTPUT['hsu']['ti'][hsu] = np.nanmean(covariates['ti'][idx])
  #DEM
  OUTPUT['hsu']['dem'][hsu] = np.nanmean(covariates['dem'][idx])
  if hydroblocks_info['clustering_version'] == 'hmc':
   #HAND
   OUTPUT['hsu']['hand'][hsu] = np.nanmean(covariates['hand'][idx])
  #Average Catchment Area
  OUTPUT['hsu']['carea'][hsu] = np.nanmean(covariates['carea'][idx])
  #Channel?
  #OUTPUT['hsu']['channel'][hsu] = stats.mode(covariates['channels'][idx])[0]

  #Land cover type 
  tmp = covariates['lc'][idx]
  tmp = tmp[tmp>=1]
  if len(tmp) >= 1 :
   OUTPUT['hsu']['land_cover'][hsu] = stats.mode(tmp)[0][0]
  else:
   OUTPUT['hsu']['land_cover'][hsu] = 17  # if there is no valid value, set to water #Noemi
      
  #Soil texture class
  OUTPUT['hsu']['soil_texture_class'][hsu] = stats.mode(covariates['TEXTURE_CLASS'][idx])[0][0]

  #Define the estimate for the model parameters
  OUTPUT['hsu']['m'][hsu] = np.nanmean(covariates['dbedrock'][idx]) #0.1 #Form of the exponential decline in conductivity (0.01-1.0)
  OUTPUT['hsu']['pksat'][hsu] = 1.0 #saturated hydraulic conductivity scalar multiplier (0.1-1.0)
  OUTPUT['hsu']['psoil'][hsu] = 1.0 #soil hydraulic properties (residual,wilting,field capacity, and porosity) (0.1-10.0)
  OUTPUT['hsu']['sdmax'][hsu] = 5.0 #maximum effective deficit of subsurface saturated zone (0.1-10.0)
  if np.max(covariates['carea'][idx]) >= 100000.0: OUTPUT['hsu']['mannings'][hsu] = 0.03 #manning's n for channel flow (0.01-0.1)
  else: OUTPUT['hsu']['mannings'][hsu] = 0.15 #manning's n for overland flow (0.01-0.8)

  # Water Management Variables
  if hydroblocks_info['water_management']['hwu_agric_flag'] == True:
   # Irrigation: 1 Irrigated, 2 paddy crop
   irrig_vec = np.copy(covariates['irrig_land'][idx].flatten())
   nii = np.nansum( irrig_vec == 1 )
   npi = np.nansum( irrig_vec == 2 )
   ttt = np.nansum( irrig_vec >= 0 )
   iratio = 0
   if ttt > 0: 
    iratio = float((nii+npi))/ttt
    if   iratio >= 0.50 and nii > npi: OUTPUT['hsu']['irrig_land'][hsu] = 1
    elif iratio >= 0.50 and nii < npi: OUTPUT['hsu']['irrig_land'][hsu] = 2
    else: OUTPUT['hsu']['irrig_land'][hsu] = 0
   else: OUTPUT['hsu']['irrig_land'][hsu] = 0
 
    # Crop Calendar
   OUTPUT['hsu']['start_growing_season'][hsu] = int(stats.mode(covariates['start_growing_season'][idx])[0][0])
   OUTPUT['hsu']['end_growing_season'][hsu] = int(stats.mode(covariates['end_growing_season'][idx])[0][0])
  
  if hydroblocks_info['water_management']['hwu_flag'] == True:
   #HRU Centroids for water management
   OUTPUT['hsu']['centroid_lons'][hsu] = np.nanmean(covariates['lons'][idx])
   OUTPUT['hsu']['centroid_lats'][hsu] = np.nanmean(covariates['lats'][idx])
   #print OUTPUT['hsu']['centroid_lons']  

 if hydroblocks_info['water_management']['hwu_flag'] == True: 
  for hsu in np.arange(nhru):
   #HRU distance between the centroids of the hru and all the other hrus 
   OUTPUT['hsu']['hru_min_dist'][hsu,:] = mgmt_funcs.calculate_min_distance(hsu, nhru, cluster_ids, covariates['lats'], covariates['lons'], OUTPUT['hsu']['centroid_lats'], OUTPUT['hsu']['centroid_lons'])
   OUTPUT['hsu']['hru_min_dist'][hsu,hsu] = 0.0
   
 return OUTPUT


def Calculate_Flow_Matrix(covariates,cluster_ids,nhru):

 #Prepare the flow matrix
 mask1 = covariates['fdir'] < 0
 covariates['fdir'][mask1] = -9999.0
 cluster_ids_copy = np.copy(cluster_ids)
 cluster_ids_copy[mask1] = np.nan
 mask2 = cluster_ids_copy < 0 #new
 covariates['fdir'][mask2] = -9999.0 #new
 cluster_ids_copy[mask2] = np.nan #new
 covariates['carea'][mask1] = -9999.0 #new
 covariates['carea'][mask2] = -9999.0 #new
 max_nhru = np.sum(cluster_ids >= 0)
 (hrus_dst,hrus_org,outlet_icoord,outlet_jcoord,outlet_hru,outlet_d8) = mt.preprocessor.calculate_connections_d8(cluster_ids_copy,covariates['fdir'],covariates['carea'],nhru,max_nhru)
 #Only use the non -9999 values
 hrus_dst = hrus_dst[hrus_dst != -9999]-1
 hrus_org = hrus_org[hrus_org != -9999]-1
 outlet_icoord = outlet_icoord[outlet_icoord != -9999]-1
 outlet_jcoord = outlet_jcoord[outlet_jcoord != -9999]-1
 outlet_hru_org = outlet_hru[outlet_hru != -9999] - 1
 outlet_d8 = outlet_d8[outlet_d8 != -9999]

 #Create hrus for the outlets
 outlet_hru_dst_summary = np.arange(nhru,nhru+np.unique(outlet_hru_org).size)
 outlet_hru_org_summary = np.unique(outlet_hru_org)
 outlet_hru_dst = np.zeros(outlet_hru_org.size)
 counts = []
 for (hru_org,hru_dst) in zip(outlet_hru_org_summary,outlet_hru_dst_summary):
  idx = outlet_hru_org == hru_org
  counts.append(np.sum(idx))
  outlet_hru_dst[idx] = hru_dst
 counts = np.array(counts)
 
 #Create a dictionary of outlet information
 outlet = {'full':{'i':outlet_icoord,'j':outlet_jcoord,'hru_org':outlet_hru_org,'hru_dst':outlet_hru_dst,'d8':outlet_d8},
           'summary':{'hru_org':outlet_hru_org_summary,'hru_dst':outlet_hru_dst_summary,'counts':counts}}

 #Update the input to create the sparse matrix
 hrus_dst[hrus_dst == -1] = hrus_org[hrus_dst == -1]

 #Prepare the sparse matrix
 flow_matrix = sparse.coo_matrix((np.ones(hrus_dst.size),(hrus_org,hrus_dst)),dtype=np.float32)
 flow_matrix = flow_matrix.tocsr()
 #Normalize the rows (sum to 1)
 fm_sum = flow_matrix.sum(axis=1)
 fm_data = flow_matrix.data
 fm_indptr = flow_matrix.indptr
 for row in range(fm_sum.size):
  fm_data[fm_indptr[row]:fm_indptr[row+1]] = fm_data[fm_indptr[row]:fm_indptr[row+1]]/fm_sum[row]
 flow_matrix.data = fm_data

 return (flow_matrix.T,outlet)

def Calculate_HRU_Connections_Matrix(covariates,cluster_ids,nhru,dx):

 #Define spatial resolution
 res = dx
 
 horg = []
 hdst = []
 #Count the connections
 for i in range(cluster_ids.shape[0]):
  for j in range(cluster_ids.shape[1]):
   h1 = cluster_ids[i,j]
   if h1 == -9999:continue
   #up
   if (i+1) < cluster_ids.shape[0]:
    h2 = cluster_ids[i+1,j]
    if h2 != -9999:
     horg.append(h1)
     hdst.append(h2)
   #down
   if (i-1) > 0:
    h2 = cluster_ids[i-1,j]
    if h2 != -9999:
     horg.append(h1)
     hdst.append(h2)
   #left
   if (j-1) > 0:
    h2 = cluster_ids[i,j-1]
    if h2 != -9999:
     horg.append(h1)
     hdst.append(cluster_ids[i,j-1])
   #right
   if (j+1) < cluster_ids.shape[1]:
    h2 = cluster_ids[i,j+1]
    if h2 != -9999:
     horg.append(h1)
     hdst.append(cluster_ids[i,j+1])
 horg = np.array(horg)
 hdst = np.array(hdst)

 #Prepare the sparse matrix
 cmatrix = sparse.coo_matrix((np.ones(hdst.size),(horg,hdst)),dtype=np.float32)
 cmatrix = cmatrix.tocsr()

 #Prepare length, width, and ksat matrices
 wmatrix = cmatrix.copy()
 wmatrix[:] = res*wmatrix[:]

 #Prepare output dictionary
 cdata = {'width':wmatrix.T,}

 return cdata

def Determine_HMC_Connectivity(h1,h2,b1,b2,tp1,tp2,hmc):

 if (h2 == -9999):return False
 if (b1 != b2) & (hmc['interridge_connectivity'] == False):return False
 if (tp1 == tp2) & (tp1 == 0) & (hmc['intervalley_connectivity'] == True):return True
 if (np.abs(tp1 - tp2) != 1) & (hmc['intraband_connectivity'] == False):return False

 return True

def Calculate_HRU_Connections_Matrix_HMC(covariates,cluster_ids,nhru,dx,HMC_info,hydroblocks_info):

 #Add pointers for simplicity
 tile_position = HMC_info['tile_position']
 basins = HMC_info['basins']
 
 #Define spatial resolution
 res = dx
 
 horg = []
 hdst = []
 #Count the connections
 for i in range(cluster_ids.shape[0]):
  for j in range(cluster_ids.shape[1]):
   h1 = cluster_ids[i,j]
   b1 = basins[i,j]
   tp1 = tile_position[i,j]
   if h1 == -9999:continue
   #up
   if (i+1) < cluster_ids.shape[0]:
    h2 = cluster_ids[i+1,j]
    b2 = basins[i+1,j]
    tp2 = tile_position[i+1,j]
    #if (h2 != -9999) & (b1 == b2) & (np.abs(tp1 - tp2) == 1):
    if Determine_HMC_Connectivity(h1,h2,b1,b2,tp1,tp2,hydroblocks_info['hmc_parameters']):
     horg.append(h1)
     hdst.append(h2)
   #down
   if (i-1) > 0:
    h2 = cluster_ids[i-1,j]
    b2 = basins[i-1,j]
    tp2 = tile_position[i-1,j]
    if Determine_HMC_Connectivity(h1,h2,b1,b2,tp1,tp2,hydroblocks_info['hmc_parameters']):
     horg.append(h1)
     hdst.append(h2)
   #left
   if (j-1) > 0:
    h2 = cluster_ids[i,j-1]
    b2 = basins[i,j-1]
    tp2 = tile_position[i,j-1]
    if Determine_HMC_Connectivity(h1,h2,b1,b2,tp1,tp2,hydroblocks_info['hmc_parameters']):
     horg.append(h1)
     hdst.append(cluster_ids[i,j-1])
   #right
   if (j+1) < cluster_ids.shape[1]:
    h2 = cluster_ids[i,j+1]
    b2 = basins[i,j+1]
    tp2 = tile_position[i,j+1]
    if Determine_HMC_Connectivity(h1,h2,b1,b2,tp1,tp2,hydroblocks_info['hmc_parameters']):
     horg.append(h1)
     hdst.append(cluster_ids[i,j+1])
 horg = np.array(horg)
 hdst = np.array(hdst)

 #Prepare the sparse matrix
 #cmatrix = sparse.coo_matrix((np.ones(hdst.size),(horg,hdst)),dtype=np.float32)
 print(np.max(horg),np.max(hdst),nhru)
 cmatrix = sparse.coo_matrix((np.ones(hdst.size),(horg,hdst)),shape=(nhru,nhru),dtype=np.float32)
 cmatrix = cmatrix.tocsr()
 print(cmatrix.shape)

 #Prepare length, width, and ksat matrices
 wmatrix = cmatrix.copy()
 wmatrix[:] = res*wmatrix[:]

 #Prepare output dictionary
 cdata = {'width':wmatrix.T,}

 return cdata

def Create_and_Curate_Covariates(wbd,hydroblocks_info):

 covariates = {}
 #Read in and curate all the covariates
 for file in wbd['files']:
  if os.path.isfile(wbd['files'][file]): 
   covariates[file] = gdal_tools.read_raster(wbd['files'][file])

 # check if lc is a covariates, and disagregate it in classes
 if 'lc' in hydroblocks_info['hmc_parameters']['intraband_clustering_covariates']:
  for lc in np.unique(covariates['lc'][covariates['mask'].astype(np.bool)]):
   if lc >= 0 :
    vnam = u'lc_%i' % lc
    masklc = (covariates['lc'] == lc)
    covariates[vnam] = np.zeros(covariates['lc'].shape)
    covariates[vnam][masklc] = 1.0
    hydroblocks_info['covariates'][vnam] = 'n'
    
 #Create lat/lon grids
 lats = np.linspace(wbd['bbox']['minlat']+wbd['bbox']['res']/2,wbd['bbox']['maxlat']-wbd['bbox']['res']/2,covariates['dem'].shape[0])
 lons = np.linspace(wbd['bbox']['minlon']+wbd['bbox']['res']/2,wbd['bbox']['maxlon']-wbd['bbox']['res']/2,covariates['dem'].shape[1])

 '''
 #Constrain the lat/lon grid by the effective resolution (4km...)
 nres = int(np.floor(90.0/30.0))
 for ilat in range(0,lats.size,nres):
  lats[ilat:ilat+nres] = np.mean(lats[ilat:ilat+nres])
 for ilon in range(0,lons.size,nres):
  lons[ilon:ilon+nres] = np.mean(lons[ilon:ilon+nres])
 '''

 #Need to fix so that it doesn't suck up all the clustering:
 lats, lons = np.meshgrid(lats, lons)
 covariates['lats'] = lats.T
 covariates['lons'] = lons.T

 #Define the mask
 mask = np.copy(covariates['mask'])
 mask[mask >= 0] = 1
 mask[mask < 0] = 0
 mask = mask.astype(np.bool)
 
 
 #Set all nans to the mean
 for var in covariates:
  if var in hydroblocks_info['hmc_parameters']['subbasin_clustering_covariates']:continue
  #covariates[var][mask <= 0] = -9999.0
  mask1 = (np.isinf(covariates[var]) == 0) & (np.isnan(covariates[var]) == 0) 
  mask0 = (np.isinf(covariates[var]) == 1) | (np.isnan(covariates[var]) == 1)
  covariates[var][mask0] = -9999.0# stats.mode(covariates[var][mask1])[0][0]

 #Set everything that is -9999 to the mean
 for var in covariates:

  m2 = ( mask == 1 ) & (covariates[var] != -9999.0)
  missing_ratio = 1.0 - np.sum(m2)/float(np.sum(mask))
  if missing_ratio > 0.99 : 
   print("Warning: Covariate %s in catchment %s has %.2f %% of nan's" % (var,hydroblocks_info['icatch'],100*missing_ratio)) # Noemi insert
   if var == 'lc': 
    mlc = (covariates[var] == -9999) & mask
    covariates[var][mlc] = 17  # Water
   if var in ['dem','fdir','sand','clay','silt','TEXTURE_CLASS','dbedrock']:
    exit('Error_clustering: %s_full_of_nans %s' % (var,hydroblocks_info['icatch']))
   #else: sys.stderr.write("Error_clustering: variable %s has %.2f %% of nan's" % (var,100*missing_ratio))

  #print var
  if var not in ['mask']:
   if var in ['fdir','nlcd','TEXTURE_CLASS','lc','irrig_land','bare30','water30','tree30','start_growing_season','end_growing_season']: 
    covariates[var] = spatial_imputation(covariates[var],-9999.0,'nearest')  
   else:
    #covariates[var] = spatial_imputation(covariates[var],-9999.0,'nearest') #faster
    covariates[var] = spatial_imputation(covariates[var],-9999.0,'linear')

 #Set everything outside of the mask to -9999
 for var in covariates:
  if var in hydroblocks_info['hmc_parameters']['subbasin_clustering_covariates']:continue
  covariates[var][mask <= 0] = -9999.0
 
 return (covariates,mask)

def spatial_imputation(array,fill_val,method):
 pos_fill = (array==fill_val)
 if np.sum(pos_fill) == 0: return array
 
 pos_mask = np.zeros(array.shape)
 pos_mask[pos_fill] = 1.0
 from skimage.morphology import binary_dilation, square
 mask_good = binary_dilation(pos_mask.astype(np.uint8),square(5))
 
 array[pos_fill]=np.nan
 array2 = np.copy(array)
 array2[(mask_good == 0)] = np.nan
  
 x = np.arange(0, array.shape[1])
 y = np.arange(0, array.shape[0])
 array = np.ma.masked_invalid(array)
 array2 = np.ma.masked_invalid(array2)
 xx, yy = np.meshgrid(x, y)
 x1 = xx[~array2.mask] #train vals
 y1 = yy[~array2.mask] #train vals
 newarr = array[~array2.mask] #train vals
 xf = xx[array.mask] # fill vals
 yf = yy[array.mask] #fill vals
 filled  = griddata((x1, y1), newarr.ravel(),(xf, yf), method=method)
 #import matplotlib.pyplot as plt
 #plt.imshow(array)
 #plt.show()
 #print array
 #plot_data(array) 
 array[array.mask] = filled  # replace fill vals
 #plt.imshow(array)
 #plt.show()
 if method in ['linear','cubic']:
  # fill the missing boundaries in nearest
  array = np.ma.masked_invalid(array)
  xf = xx[array.mask] # fill vals
  yf = yy[array.mask] #fill vals
  filled  = griddata((x1, y1), newarr.ravel(),(xf, yf), method='nearest')
  array[array.mask] = filled
 return np.ma.filled(array)

def Create_Clusters_And_Connections(workspace,wbd,output,input_dir,nhru,info,hydroblocks_info):
 
 #Retrieve some metadata
 metadata = gdal_tools.retrieve_metadata(wbd['files']['mask'])
 resx = metadata['resx']

 print("Creating and curating the covariates")
 (covariates,mask) = Create_and_Curate_Covariates(wbd,hydroblocks_info)
 
 #Determine the HRUs (clustering if semidistributed; grid cell if fully distributed)
 print("Computing the HRUs")
 print(hydroblocks_info['clustering_version'])
 if hydroblocks_info['model_type'] == 'semi':
  if hydroblocks_info['clustering_version'] == 'chaney2016':
   (cluster_ids,nhru) = Compute_HRUs_Semidistributed_Kmeans(covariates,mask,nhru,hydroblocks_info,wbd)
  elif hydroblocks_info['clustering_version'] == 'hmc':
   (cluster_ids,nhru,hand,HMC_info,covariates) = Compute_HRUs_Semidistributed_HMC(covariates,mask,hydroblocks_info,wbd,resx)
   covariates['hand'] = hand
 elif hydroblocks_info['model_type'] == 'full':
  nhru = np.sum(mask == True)
  (cluster_ids,) = Compute_HRUs_Fulldistributed(covariates,mask,nhru)
 hydroblocks_info['nhru'] = nhru
  
 #Create the netcdf file
 file_netcdf = hydroblocks_info['input_file']
 hydroblocks_info['input_fp'] = nc.Dataset(file_netcdf, 'w', format='NETCDF4')

 #Create the dimensions (netcdf)
 idate = hydroblocks_info['idate']
 fdate = hydroblocks_info['fdate']
 dt = hydroblocks_info['dt']
 ntime = 24*3600*((fdate - idate).days+1)/dt
 nhsu = hydroblocks_info['nhru']
 hydroblocks_info['input_fp'].createDimension('hsu',nhsu)
 hydroblocks_info['input_fp'].createDimension('time',ntime)
 
 #Create the groups (netcdf)
 hydroblocks_info['input_fp'].createGroup('meteorology')
 hydroblocks_info['input_fp'].createGroup('water_use')

 #Prepare the flow matrix (dynamic topmodel)
 print("Calculating the flow matrix")
 (flow_matrix,outlet) = Calculate_Flow_Matrix(covariates,cluster_ids,nhru)

 #Prepare the hru connections matrix (darcy clusters)
 if hydroblocks_info['clustering_version'] == 'chaney2016':
  cmatrix = Calculate_HRU_Connections_Matrix(covariates,cluster_ids,nhru,resx)
 elif hydroblocks_info['clustering_version'] == 'hmc':
  cmatrix = Calculate_HRU_Connections_Matrix_HMC(covariates,cluster_ids,nhru,resx,HMC_info,hydroblocks_info)

 #Define the metadata
 metadata = gdal_tools.retrieve_metadata(wbd['files']['dem'])

 #Make the output dictionary for the basin
 OUTPUT = {'hsu':{},'metadata':metadata,'mask':mask,'flow_matrix':flow_matrix,'cmatrix':cmatrix}
 OUTPUT['outlet'] = outlet

 #Remember the map of hrus
 OUTPUT['hsu_map'] = cluster_ids

 #Assign the model parameters
 print("Assigning the model parameters")
 if hydroblocks_info['model_type'] == 'semi':
  OUTPUT = Assign_Parameters_Semidistributed(covariates,metadata,hydroblocks_info,OUTPUT,cluster_ids,mask)
 elif hydroblocks_info['model_type'] == 'full':
  OUTPUT = Assign_Parameters_Fulldistributed(covariates,metadata,hydroblocks_info,OUTPUT,cluster_ids,mask)

 #Add the new number of clusters
 OUTPUT['nhru'] = nhru
 OUTPUT['mask'] = mask

 return OUTPUT

def Prepare_Meteorology_Fulldistributed(workspace,wbd,OUTPUT,input_dir,info,hydroblocks_info):

 #Assign other variables
 mask = OUTPUT['mask']

 mapping_info = {}
 #Calculate the fine to coarse scale mapping
 for data_var in wbd['files_meteorology']:

  #Define the variable name
  var = data_var#data_var.split('_')[1]
  mapping_info[var] = {}

  #Read in the coarse and fine mapping
  file_coarse = '%s/%s_ea_coarse.tif' % (workspace,var)
  file_fine = '%s/%s_ea_fine.tif' % (workspace,var)
  mask_coarse = gdal_tools.read_raster(file_coarse)
  mask_fine = gdal_tools.read_raster(file_fine)
  nlat = mask_coarse.shape[0]
  nlon = mask_coarse.shape[1]

  print(data_var,"Creating the i and j mapping")
  #Create maps of i and j for mapping
  coords = {'i':np.zeros(mask_fine.shape,dtype=np.int),
            'j':np.zeros(mask_fine.shape,dtype=np.int)}
  for value in np.unique(mask_coarse):
   if value < 0:continue
   idx_fine = mask_fine == value
   idx_coarse = np.where(mask_coarse == value)
   coords['i'][idx_fine] = nlat - idx_coarse[0] - 1 #Careful
   coords['j'][idx_fine] = idx_coarse[1]
  coords['i'] = coords['i'][mask]
  coords['j'] = coords['j'][mask]

  print(data_var,"Extracting all the data")
  #Extract all of the data for that variable
  idate = info['time_info']['startdate']
  fdate = info['time_info']['enddate']
  nt = 24*((fdate - idate).days+1)
  var = data_var#data_var.split('_')[1]
  date = idate
  file = wbd['files_meteorology'][data_var]
  fp = nc.Dataset(file)
  #Determine the time steps to retrieve
  dates = nc.num2date(fp.variables['t'][:],units='hours since %02d-%02d-%02d 00:00:00' % (idate.year,idate.month,idate.day))
  mask_dates = (dates >= idate) & (dates <= fdate)
  data = np.ma.getdata(fp.variables[var][mask_dates])
  fp.close()

  print(data_var,"Assigning the data")
  #Create the variable
  grp = hydroblocks_info['input_fp'].groups['meteorology']
  grp.createVariable(var,'f4',('time','hsu'))
  #Place all the data per time step
  tmp = np.zeros(np.sum(mask))
  for itime in np.arange(data.shape[0]):
   tmp[:] = data[itime,coords['i'],coords['j']]
   #Write the timestep
   grp.variables[var][itime,:] = tmp[:]

 return

def Prepare_Meteorology_Semidistributed(workspace,wbd,OUTPUT,input_dir,info,hydroblocks_info):

 #Define the mapping directory
 mapping_info = {}
 #Calculate the fine to coarse scale mapping
 for data_var in wbd['files_meteorology']:
  
  #Define the variable name
  var = data_var#data_var.split('_')[1]
  mapping_info[var] = {}

  #Read in the coarse and fine mapping
  file_coarse = '%s/%s_latlon_coarse.tif' % (workspace,data_var)
  file_fine = '%s/%s_ea_fine.tif' % (workspace,data_var)
  mask_coarse = gdal_tools.read_raster(file_coarse)
  mask_fine = gdal_tools.read_raster(file_fine)
  nlat = mask_coarse.shape[0]
  nlon = mask_coarse.shape[1]

  #Compute the mapping for each hsu
  for hsu in np.arange(hydroblocks_info['nhru']):
   idx = OUTPUT['hsu_map'] == hsu
   #print "Catch:",hydroblocks_info['icatch'], "HRU: ", mask_fine[idx].astype(np.int)
   icells = np.unique(mask_fine[idx][mask_fine[idx] != -9999.0].astype(np.int))   # Add != -9999 for unique and bicount - Noemi
   counts = np.bincount(mask_fine[idx][mask_fine[idx] != -9999.0].astype(np.int))
   coords,pcts = [],[]
   for icell in icells:
    ilat = int(np.floor(icell/mask_coarse.shape[1]))
    jlat = icell - ilat*mask_coarse.shape[1]
    #ilat = int(mask_coarse.shape[0] - ilat - 1) #CAREFUL
    pct = float(counts[icell])/float(np.sum(counts))
    coords.append([ilat,jlat])
    pcts.append(pct)
   pcts = np.array(pcts)
   coords = list(np.array(coords).T)
   mapping_info[var][hsu] = {'pcts':pcts,'coords':coords}

 #Iterate through variable creating forcing product per HSU
 idate = info['time_info']['startdate']
 fdate = info['time_info']['enddate']
 dt = info['time_info']['dt']
 nt = int(3600*24/dt)*((fdate - idate).days+1)
 #Create structured array
 meteorology = {}
 for data_var in wbd['files_meteorology']:
  meteorology[data_var] = np.zeros((nt,hydroblocks_info['nhru']))
 #Load data into structured array
 for data_var in wbd['files_meteorology']:
  var = data_var#data_var.split('_')[1]
  date = idate
  file = wbd['files_meteorology'][data_var]
  fp = nc.Dataset(file)
  #fp = h5py.File(file)
  
  #Determine the time steps to retrieve
  #fidate = ' '.join(fp.variables['t'].units.split(' ')[2::])
  #dates = nc.num2date(fp.variables['t'][:],units='hours since %s' % (fidate))  # num2date doesnt work for step of 3h.
  nc_step = int(fp.variables['t'].units.split(' ')[0].split('h')[0])
  nc_idate = np.array(fp.variables['t'].units.split(' ')[2].split('-'))
  nc_nt = len(fp.variables['t'][:])
  dates = [datetime.datetime(int(nc_idate[0]),int(nc_idate[1]),int(nc_idate[2]))]
  for it in range(1,nc_nt): dates.append(dates[0] + datetime.timedelta(hours=it*nc_step))
  dates=np.array(dates)
  startdate = info['time_info']['startdate']
  enddate = info['time_info']['enddate']
  mask_dates = (dates >= startdate) & (dates <= enddate)
  data = np.ma.getdata(fp.variables[var][mask_dates,:,:])
  fp.close()

  #Assing to hsus
  for hsu in mapping_info[var]:
   #print data_var,data, data.shape, hsu,mapping_info[var][hsu]['pcts'],mapping_info[var][hsu]['coords'],
   #print hsu, var, data.shape, hsu,mapping_info[var][hsu]['pcts'],mapping_info[var][hsu]['coords']
   pcts = mapping_info[var][hsu]['pcts']
   coords = mapping_info[var][hsu]['coords']
   coords[0][coords[0] >= data.shape[1]] = data.shape[1] - 1
   coords[1][coords[1] >= data.shape[2]] = data.shape[2] - 1
   tmp = data[:,coords[0],coords[1]]
   #m1 = tmp < -999
   #m2 = tmp > -999
   tmp = pcts*tmp
   meteorology[data_var][:,hsu] = np.sum(tmp,axis=1)
   #print data_var,np.unique(meteorology[data_var][:,:])

  #Write the meteorology to the netcdf file (single chunk for now...)
  grp = hydroblocks_info['input_fp'].groups['meteorology']
  grp.createVariable(var,'f4',('time','hsu'))#,zlib=True)
  grp.variables[data_var][:] = meteorology[data_var][:]


 #Add time information
 dates = []
 date = idate
 while date <= fdate:
  dates.append(date)
  date = date + datetime.timedelta(seconds=dt)
 dates = np.array(dates)
 var = grp.createVariable('time','f8',('time',))
 var.units = 'hours since %4d-01-01' % idate.year
 var.calendar = 'standard'
 dates = nc.date2num(dates,units=var.units,calendar=var.calendar)
 var[:] = dates[:]


 return


def Prepare_Water_Use_Semidistributed(workspace,wbd,OUTPUT,input_dir,info,hydroblocks_info):

 #Define the mapping directory
 mapping_info = {}
 
 #Calculate the fine to coarse scale mapping
 for data_var in wbd['files_water_use']:

  #Define the variable name
  var = data_var#data_var.split('_')[1]
  mapping_info[var] = {}

  #Read in the coarse and fine mapping
  file_coarse = '%s/%s_latlon_coarse.tif' % (workspace,data_var)
  file_fine = '%s/%s_ea_fine.tif' % (workspace,data_var)
  mask_coarse = gdal_tools.read_raster(file_coarse)
  mask_fine = gdal_tools.read_raster(file_fine)
  md = gdal_tools.retrieve_metadata(file_fine)
  md['nodata'] = -9999.0
  nlat = mask_coarse.shape[0]
  nlon = mask_coarse.shape[1]

  # NOAH Land Cover code for each water use sector
  water_use_land_cover = {'industrial':[13],'domestic':[6,7,8,9,10,13],'livestock':[6,7,8,9,10], "agriculture":[12,14]}
  
  # 1. Identify location of each type of water use
  # HRU lc map
  hrus_lc = np.copy(OUTPUT['hsu_map'])
  for hsu in np.arange(hydroblocks_info['nhru']): 
   idx = OUTPUT['hsu_map'] == hsu
   hrus_lc[idx]= OUTPUT['hsu']['land_cover'][hsu]
  m = hrus_lc == -9999.0
  lc = gdal_tools.read_raster('%s/lc_ea.tif' % (workspace))
  hrus_lc[m] = lc[m]
 
  for l in np.unique(hrus_lc): 
   idx = hrus_lc == l
   if l in water_use_land_cover[data_var]:
    hrus_lc[idx]=1.0
   else:
    hrus_lc[idx]=0.0
  
  wuse_lc_ea_file = '%s/%s_lc_ea.tif' % (workspace,data_var)
  gdal_tools.write_raster(wuse_lc_ea_file,md,hrus_lc)
  fine_size = hrus_lc.shape
  fine_res = abs(md['resx'])
  
  # Get the coarse water use info and regrid the fine lc to coarser lc
  wuse_lc_coarse_file = '%s/%s_latlon_coarse.tif' % (workspace,data_var)
  md = gdal_tools.retrieve_metadata(wuse_lc_coarse_file)
  minx = md['minx']
  miny = md['miny']
  maxx = md['maxx']
  maxy = md['maxy']
  res  = abs(md['resx'])
  lproj = md['proj4']+' +datum=WGS84'
  file_in = wuse_lc_ea_file
  file_out = '%s/%s_area_latlon_coarse.tif' % (workspace,data_var)
  os.system('gdalwarp -overwrite -t_srs \'%s\' -ot Float32 -dstnodata -9999 -tr %f %f -te %f %f %f %f -r average -q %s %s ' % (lproj,res,res,minx,miny,maxx,maxy,file_in,file_out))

  # Calculate the equivalent area of each grid
  data = gdal_tools.read_raster(file_out)
  md['nodata'] = -9999.0
  data[ data == md['nodata'] ] = 0.0
  coarse_size = data.shape
  #print 'res_fine', fine_res  #Should be in meters
  data_grid_area = fine_res*fine_res*(fine_size[0]/float(coarse_size[0]))*(fine_size[1]/float(coarse_size[1]))
  data = data*data_grid_area
  gdal_tools.write_raster(file_out,md,data)

  #hru_map = np.copy(OUTPUT['hsu_map'])
  #hru_map[hru_map<0]=np.nan
  #plt.imshow(hru_map); plt.show()
  #plt.imshow(hrus_lc); plt.show()
  #plt.imshow(data); plt.show()
  
  #Compute the mapping for each hsu
  for hsu in np.arange(hydroblocks_info['nhru']):
   idx = OUTPUT['hsu_map'] == hsu
   #print "Catch:",hydroblocks_info['icatch'], "HRU: ", mask_fine[idx].astype(np.int)
   icells = np.unique(mask_fine[idx][mask_fine[idx] != -9999.0].astype(np.int))   # Add != -9999 for unique and bicount - Noemi
   counts = np.bincount(mask_fine[idx][mask_fine[idx] != -9999.0].astype(np.int))
   coords,pcts = [],[]
   for icell in icells:
    ilat = int(np.floor(icell/mask_coarse.shape[1]))
    jlat = icell - ilat*mask_coarse.shape[1]
    #ilat = int(mask_coarse.shape[0] - ilat - 1) #CAREFUL
    pct = float(counts[icell])/float(np.sum(counts))
    coords.append([ilat,jlat])
    pcts.append(pct)
   pcts = np.array(pcts)
   coords = list(np.array(coords).T)
   mapping_info[var][hsu] = {'pcts':pcts,'coords':coords}

 #Iterate through variable creating water use product per HSU
 idate = info['time_info']['startdate']
 fdate = info['time_info']['enddate']
 dt = info['time_info']['dt']
 nt = int(3600*24/dt)*((fdate - idate).days+1)

 #Create structured array
 water_use = {}
 for data_var in wbd['files_water_use']:
  water_use[data_var] = np.zeros((nt,hydroblocks_info['nhru']))

 #Load data into structured array
 for data_var in wbd['files_water_use']:
  var = data_var
  date = idate
  file = wbd['files_water_use'][data_var]
  fp = nc.Dataset(file)
  #Determine the time steps to retrieve
  #fidate = ' '.join(fp.variables['t'].units.split(' ')[2::])
  #dates = nc.num2date(fp.variables['t'][:],units='hours since %s' % fidate)
  #mask_dates = (dates >= idate) & (dates <= fdate)
  nc_step = int(fp.variables['t'].units.split(' ')[0].split('h')[0])
  nc_idate = np.array(fp.variables['t'].units.split(' ')[2].split('-'))
  nc_nt = len(fp.variables['t'][:])
  dates = [datetime.datetime(int(nc_idate[0]),int(nc_idate[1]),int(nc_idate[2]))]
  for it in range(1,nc_nt): dates.append(dates[0] + datetime.timedelta(hours=it*nc_step))
  dates=np.array(dates)
  startdate = info['time_info']['startdate']
  enddate  = info['time_info']['enddate']
  mask_dates = (dates >= startdate) & (dates <= enddate)
  data = np.ma.getdata(fp.variables[var][mask_dates,:,:])
  fp.close()
  
  # convert water use volume from m3 to m3/m2
  file_out = '%s/%s_area_latlon_coarse.tif' % (workspace,data_var)
  wuse_area = gdal_tools.read_raster(file_out)
  m = ( wuse_area == 0.0 )
  data[:,m] = 0.0
  wuse_area[m] = 1.0
  data = data/wuse_area
 

  #Assing to hsus
  for hsu in mapping_info[var]:
   if OUTPUT['hsu']['land_cover'][hsu] in water_use_land_cover[data_var]:
    #print data_var,data, data.shape, hsu,mapping_info[var][hsu]['pcts'],mapping_info[var][hsu]['coords'],
    pcts = mapping_info[var][hsu]['pcts']
    coords = mapping_info[var][hsu]['coords']
    coords[0][coords[0] >= data.shape[1]] = data.shape[1] - 1
    coords[1][coords[1] >= data.shape[2]] = data.shape[2] - 1
    tmp = data[:,coords[0],coords[1]]
    tmp = pcts*tmp
    water_use[data_var][:,hsu] = np.sum(tmp,axis=1)  # final variable m3/m2/s --> m/s of water demand
    #print hsu, data_var, OUTPUT['hsu']['land_cover'][hsu], water_use[data_var][:,hsu]
   else:
    water_use[data_var][:,hsu] = 0.0

  #Write the water use the netcdf file (single chunk for now...)
  grp = hydroblocks_info['input_fp'].groups['water_use']
  grp.createVariable(var,'f4',('time','hsu'))#,zlib=True)
  grp.variables[data_var][:] = water_use[data_var][:]

 if hydroblocks_info['water_management']['hwu_flag']:
  if len(wbd['files_water_use']) > 1 :
   #Add time information
   dates = []
   date = idate
   while date <= fdate:
    dates.append(date)
    date = date + datetime.timedelta(seconds=dt)
   dates = np.array(dates)
   var = grp.createVariable('time','f8',('time',))
   var.units = 'hours since %4d-01-01' % idate.year
   var.calendar = 'standard'
   dates = nc.date2num(dates,units=var.units,calendar=var.calendar)
   var[:] = dates[:]

 return



def Read_Metadata_File(file):

 import json
 metadata = json.load(open(file))

 return metadata

