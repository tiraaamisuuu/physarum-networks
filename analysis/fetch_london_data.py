#!/usr/bin/env python3
"""Download documented geographic inputs; application runs use the frozen local copy."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

import numpy as np
from pyproj import Transformer
import pyproj

ROOT=Path(__file__).resolve().parents[1]
SELECTED = """940GZZLUBST 940GZZLUPAC 940GZZLUNHG 940GZZLUSBC 940GZZLUHSD 940GZZLUECT
940GZZLUSKS 940GZZLUKNB 940GZZLUVIC 940GZZLUVXL 940GZZLUWLO 940GZZLUWSM 940GZZLUEMB
940GZZLUCHX 940GZZLUPCC 940GZZLUGPK 940GZZLUOXC 940GZZLUBND 940GZZLUTCR 940GZZLUHBN
940GZZLUFCN 940GZZLUEUS 940GZZLUKSX 940GZZLUAGL 940GZZLUODS 940GZZLULVT 940GZZLUBNK
940GZZLUMGT 940GZZLUSPU 940GZZLUBKF 940GZZLUTMP 940GZZLUTWH 940GZZLUADE 940GZZLUWPL
940GZZLUMED 940GZZLUSTD 940GZZLUCYF 940GZZLUCWR 940GZZLUBMY 940GZZLULNB 940GZZLUSWK
940GZZLUEAC 940GZZLUKNG 940GZZLUOVL 940GZZLUSKW 940GZZBPSUST""".split()
OSM_QUERY='[out:json][timeout:20];way["waterway"="river"]["name"~"Thames"](51.45,-0.25,51.57,0.05);out geom;'


def get(url,cache,refresh=False):
    if cache.exists() and not refresh:
        return cache.read_bytes()
    request=urllib.request.Request(url,headers={'User-Agent':'PhysarumNetworksResearch/0.1 (github.com/tiraaamisuuu/physarum-networks)','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=35) as response:
        data=response.read()
    cache.parent.mkdir(parents=True,exist_ok=True)
    cache.write_bytes(data)
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    cache=ROOT/'tmp/london';cache.mkdir(parents=True,exist_ok=True)
    sources=[]
    def read(url,name,attribution,license):
        raw=get(url,cache/name,args.refresh)
        sources.append({'url':url,'raw_sha256':hashlib.sha256(raw).hexdigest(),'attribution':attribution,'licence':license,
                        'retrieved_utc':datetime.fromtimestamp((cache/name).stat().st_mtime,timezone.utc).isoformat()})
        return json.loads(raw)
    tfl=read('https://api.tfl.gov.uk/StopPoint/Mode/tube','tfl-stations.json','Contains Transport for London data','TfL Transport Data Service terms: https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service')
    project=Transformer.from_crs('EPSG:4326','EPSG:27700',always_xy=True)
    stations=[]
    for stop in tfl['stopPoints']:
        if stop.get('stopType')!='NaptanMetroStation' or not stop['id'].startswith('940G'):
            continue
        x,y=project.transform(stop['lon'],stop['lat'])
        stations.append({'tfl_id':stop['id'],'name':stop['commonName'].replace(' Underground Station',''),
                         'lat':stop['lat'],'lon':stop['lon'],'x':x/1000,'y':y/1000,'kind':'station'})
    stations.sort(key=lambda node:node['name'])
    lookup={node['tfl_id']:node for node in stations}
    missing=set(SELECTED)-set(lookup)
    if missing:raise ValueError(f'Missing requested stations: {missing}')
    selected=[lookup[key] for key in SELECTED]
    url='https://ovp.dresel.systems/api/interpreter?'+urllib.parse.urlencode({'data':OSM_QUERY})
    osm=read(url,'thames-osm.json','© OpenStreetMap contributors','ODbL 1.0: https://www.openstreetmap.org/copyright')
    river=[]
    for way in osm['elements']:
        geometry=way.get('geometry',[])
        if len(geometry)<2:continue
        coordinates=[project.transform(point['lon'],point['lat']) for point in geometry]
        river.append({'osm_way_id':way['id'],'xy_km':[[x/1000,y/1000] for x,y in coordinates]})
    if not river:raise ValueError('No Thames geometry received; refusing to invent a river.')
    xs=[node['x'] for node in selected];ys=[node['y'] for node in selected]
    gx=np.linspace(min(xs)-1,max(xs)+1,19);gy=np.linspace(min(ys)-1,max(ys)+1,13)
    xx,yy=np.meshgrid(gx,gy)
    inverse=Transformer.from_crs('EPSG:27700','EPSG:4326',always_xy=True)
    lons,lats=inverse.transform(xx.ravel()*1000,yy.ravel()*1000)
    heights=[]
    for start in range(0,len(lats),100):
        query=urllib.parse.urlencode({'latitude':','.join(f'{v:.6f}' for v in lats[start:start+100]),
                                     'longitude':','.join(f'{v:.6f}' for v in lons[start:start+100])})
        result=read('https://api.open-meteo.com/v1/elevation?'+query,f'elevation-{start}.json',
                    'Copernicus DEM GLO-90, distributed by Open-Meteo','Open-Meteo CC BY 4.0; see https://open-meteo.com/en/docs/elevation-api')
        heights.extend(result['elevation'])
    z=np.asarray(heights,dtype=float).reshape(xx.shape)
    if not np.isfinite(z).all():raise ValueError('Elevation data are incomplete.')
    operation=project.get_last_used_operation()
    data={'schema_version':1,'name':'London Tube exploratory connections',
          'retrieved_utc':max(source['retrieved_utc'] for source in sources),'prepared_utc':datetime.now(timezone.utc).isoformat(),
          'projection':{'crs':'EPSG:27700','units':'km','pyproj':pyproj.__version__,
                        'operation':operation.description,'advertised_accuracy_m':operation.accuracy},
          'station_catalog':stations,'default_station_ids':SELECTED,'river':river,
          'coverage_bounds_lat_lon':[51.45,-0.25,51.57,0.05],
          'elevation':{'x':gx.tolist(),'y':gy.tolist(),'metres':z.tolist(),'role':'visual_context_only',
                       'sample_spacing_km':[float(gx[1]-gx[0]),float(gy[1]-gy[0])]},
          'sources':sources,'assumptions':['Selected station subset, not the complete Tube system.',
            'No passenger-demand data: station-pair demand is synthetic.',
            'Elevation is visual context only; underground construction cost is not inferred from surface height.',
            'Thames is an OSM centreline; its plotted width is symbolic.']}
    out=ROOT/'data/london/geography.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    print(f'Saved {len(stations)} official station entries; {len(selected)} selected; {len(river)} Thames ways; {z.size} elevation samples.')


if __name__=='__main__':main()
