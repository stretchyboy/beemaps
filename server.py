from flask import Flask, render_template, request
import folium
from folium import plugins
import json
import io, os
import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from folium.plugins import HeatMap
from numpy import result_type
import requests
import pandas as pd

RADIUS = 500

app = Flask(__name__)

app.secret_key = os.environ.get('APP_SECRET_KEY')

def call_api(url: str) -> dict:
    postcode_response = requests.get(url)
    return postcode_response.json()

def get_data(postcode):
    url = f"http://api.getthedata.com/postcode/{postcode}"
    req = requests.get(url)

    if req.json()["status"] == "match":
        results = req.json()["data"]
        latitude = results.get("latitude")
        longitude = results.get("longitude")
    else:
        latitude = None
        longitude = None

    return latitude, longitude

def get_columns(code):
    api_param = code
    return get_data(api_param)

def get_latlong(text):
    data = io.StringIO(text.replace("\t",","))
    print("get_latlong text", text, "data", data)
    df = pd.read_csv(data, dtype=object)
    df.drop_duplicates()
    df = df.dropna(axis=0)

    if ("Latitude" not in df) and ("Postcode" in df):    
        df[["Latitude", "Longitude"]] = df.apply(
            lambda row: get_columns(row["Postcode"]), axis=1, result_type="expand"
        )
    
    df = df.dropna(axis=0)
    print("get_latlong df", df)
    
    return df

@app.route('/')
def index():
  return render_template("index.html", form={})
  
@app.route('/map', methods=['POST'])
def showmap():
  #print("request.form", request.form)
  if (request.form['password'] != app.secret_key):
    print("Password Didn't Match")
    return render_template("index.html", form=request.form)
  
  start_coords = (46.9540700, 142.7360300);
  
  m = folium.Map(
      location=start_coords, 
      zoom_start=14, 
      #tiles="Stamen Terrain",
      width="100%", height="100%",
      control_scale=True,
  );
  
  pins = 0
  circles = 0


  if request.form['points1']:
    #print("request.form", request.form)
    df = get_latlong(request.form['points1']) 
    #print("df", df)
    
    if request.form["renderer1"] == "Heatmap":
      heat_data = [[row["Latitude"],row["Longitude"]] for index, row in df.iterrows()]
      HeatMap(heat_data).add_to(m)
    
    else: 
      for index, row in df.iterrows():
        #print("row", row)
        texts = []
        if "Postcode" in request.form["renderer1"] and "Postcode" in df:
          texts.append(row['Postcode'])
        if "Label" in df:
          texts.append(row['Label'])

        permanent = "Label" in request.form["renderer1"]

        if "Pin" in request.form["renderer1"]:
          folium.Marker( 
            location=[row["Latitude"],row["Longitude"]],
            tooltip = folium.Tooltip( ": ".join(texts), permanent=permanent),
            icon=folium.Icon(
              color=request.form["colour1"].lower(),
              icon=request.form["icon1"].lower(),
            )).add_to( m )
        
        if "Hornet Range" in request.form["renderer1"]:
          folium.Circle(
            location=[row["Latitude"],row["Longitude"]],
            radius = RADIUS,
            color="black",
            weight=1,
            fill_opacity=0.2,
            opacity=1,
            fill_color=request.form["colour1"].lower(),
            fill=False,  # gets overridden by fill_color
            tooltip=folium.Tooltip( ": ".join(texts), permanent=permanent),
          ).add_to(m)
              

  m.fit_bounds(m.get_bounds(), padding=(30, 30))

  folium.TileLayer('cartodbpositron').add_to(m)
  folium.TileLayer('openstreetmap').add_to(m)

  # Add the option to switch tiles
  folium.LayerControl().add_to(m)

  fs = plugins.Fullscreen().add_to(m)

  gc = plugins.Geocoder(collapsed=True, position='topleft', add_marker=True).add_to(m)

  mc = plugins.MeasureControl( position='topleft').add_to(m)

  return m._repr_html_()
  
if __name__ == '__main__':
    app.run(debug=True)
