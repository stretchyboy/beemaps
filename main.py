from cgi import test
from flask import Flask, render_template, request, flash, jsonify
import folium
from folium import plugins
import json
import io, os
import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from folium.plugins import HeatMap
from numpy import result_type
import requests
from flask_bootstrap import Bootstrap5
import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
import pgeocode

from flask_wtf import FlaskForm, CSRFProtect
from wtforms import PasswordField, StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length

import demo_points

nomi = pgeocode.Nominatim('gb')
        
RADIUS = 500

app = Flask(__name__)

app.secret_key = os.environ.get('APP_SECRET_KEY')

# Bootstrap-Flask requires this line
bootstrap = Bootstrap5(app)
# Flask-WTF requires this line
csrf = CSRFProtect(app)

#MARKERS = ["None", "Heatmap","Pins", "Pins with Labels", "Pins with Postcodes and Labels", "Hornet Range", "Hornet Range with Labels", "Hornet Range with Postcodes and Labels"]
MARKERS = ["None", "Heatmap","Pins", "Range 500m", "Range 750m", "Range 1km"]
COLOURS = ["Red","Blue","Green","Orange", "Purple"]
ICONS = ["None","OK","Flag"]
YESNO = ["No", "Yes"]

TEST = False

class MapForm(FlaskForm):
    renderer1 = SelectField('Marker1', choices=MARKERS, default="Heatmap", validators=[DataRequired()])
    colour1 = SelectField('Colour', choices=COLOURS, default="None", validators=[DataRequired()])
    icon1 = SelectField('Icon', choices=ICONS, validators=[DataRequired()])
    postcode1 = SelectField('Postcode in Label', choices=YESNO, validators=[DataRequired(), ])
    label1 = SelectField('Label always on', choices=YESNO, validators=[DataRequired(), ])
    points1 = TextAreaField("Points", 
                            description='"Latitude, Longitude /Postcode (,Label)" can use tabs instead of ",", Must include header row',
                            validators=[DataRequired()],
                            default = demo_points.lat_lon_text if TEST else None
                            )

    renderer2 = SelectField('Marker2', choices=MARKERS, default="Pins", validators=[DataRequired()])
    colour2 = SelectField('Colour', choices=COLOURS, default="Blue", validators=[DataRequired()])
    icon2 = SelectField('Icon', choices=ICONS, default="OK", validators=[DataRequired()])
    postcode2 = SelectField('Postcode in Label', choices=YESNO, validators=[DataRequired(), ])
    label2 = SelectField('Label always on', choices=YESNO, validators=[DataRequired(), ])
    points2 = TextAreaField("Points", 
                            default = demo_points.postcode_text if TEST else None
                            #description='"Latitude, Longitude /Postcode (,Label)" can use tabs instead of ",", Must include header row',
                            #validators=[DataRequired()]
                            )

    renderer3 = SelectField('Marker3', choices=MARKERS, default="Pins", validators=[DataRequired()])
    colour3 = SelectField('Colour', choices=COLOURS, default="Green", validators=[DataRequired()])
    icon3 = SelectField('Icon', choices=ICONS, default="Flag", validators=[DataRequired()])
    postcode3 = SelectField('Postcode in Label', choices=YESNO, validators=[DataRequired(), ])
    label3 = SelectField('Label always on', choices=YESNO, validators=[DataRequired(), ])
    points3 = TextAreaField("Points", 
                            default = demo_points.postcode_labeled2 if TEST else None
                            #description='"Latitude, Longitude /Postcode (,Label)" can use tabs instead of ",", Must include header row',
                            #validators=[DataRequired()]
                            )

    password = PasswordField("Password")
    preview = SubmitField('Preview')
    submit = SubmitField('Make Map')


def call_api(url: str) -> dict:
    postcode_response = requests.get(url)
    return postcode_response.json()

postcodecache = {}

def get_data(postcode):
    latitude = None
    longitude = None
    if postcode in postcodecache:
      latitude = postcodecache[postcode]["latitude"]
      longitude = postcodecache[postcode]["longitude"]
      return latitude, longitude
    
    url = f"http://api.getthedata.com/postcode/{postcode}"
    req = requests.get(url)

    if req.json()["status"] == "match" :
      if req.json()["match_type"] == "unit_postcode":
        results = req.json()["data"]
        latitude = results.get("latitude")
        longitude = results.get("longitude")
        postcodecache[postcode] = {
          "latitude":  latitude,
          "longitude" : longitude
        }
      else:
        dat = nomi.query_postal_code(postcode)
        latitude = dat["latitude"]
        longitude = dat["longitude"]
    

    return latitude, longitude

def get_columns(code):
    api_param = code
    return get_data(api_param)

def get_latlong(text):
    data = io.StringIO(re.sub("[ ][ ]+", "\t", text).replace("\t",","))
    df = pd.read_csv(data, dtype=object)
    df.drop_duplicates()
    df = df.dropna(axis=0)

    if ("Latitude" not in df) and ("Postcode" in df):    
      try:
        df[["Latitude", "Longitude"]] = df.apply(
            lambda row: get_columns(row["Postcode"]), axis=1, result_type="expand"
        )
      except Exception as e:
          flash('Postcode Conversion failed : '+ str(e))
          return []
      
    df = df.dropna(axis=0)
    return df

def get_map(formdata):   
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
  
    for i in range(1,4):
      if formdata[f'points{i}']:
        df = get_latlong(formdata[f'points{i}']) 
        
        if (len(df) == 0):
           continue

        if formdata[f"renderer{i}"] == "Heatmap":
          heat_data = [[row["Latitude"],row["Longitude"]] for index, row in df.iterrows() if "Latitude" in row and "Longitude" in row]
          HeatMap(heat_data).add_to(m)
        
        else: 
          for index, row in df.iterrows():
            if "Latitude" not in row or "Longitude" not in row:
              flash('Latitude or Longitude not in row')
              continue
               
            #print("row", row)
            texts = []

            if formdata[f"postcode{i}"] == "Yes" and "Postcode" in row:
            #if "Postcode" in formdata[f"renderer{i}"] and "Postcode" in row:
              texts.append(row['Postcode'])

            if "Label" in row:
              texts.append(row['Label'])

            tooltip = None
            #permanent = "Label" in formdata[f"renderer{i}"]
            
            #print(f"label{i}",formdata[f"label{i}"])
            permanent = formdata[f"label{i}"] == "Yes"
            
            if len(texts):
              tooltip = folium.Tooltip( ": ".join(texts), permanent=permanent)

            if "Pin" in formdata[f"renderer{i}"]:
              folium.Marker( 
                location=[row["Latitude"],row["Longitude"]],
                tooltip = tooltip,
                icon=folium.Icon(
                  color=formdata[f"colour{i}"].lower(),
                  icon=formdata[f"icon{i}"].lower(),
                )).add_to( m )
            
            if "Range" in formdata[f"renderer{i}"]:
              if formdata[f"renderer{i}"] == "Range 500m":
                 RADIUS = 500
              if formdata[f"renderer{i}"] == "Range 750m":
                 RADIUS = 750
              if formdata[f"renderer{i}"] == "Range 1km":
                 RADIUS = 1000
              folium.Circle(
                location=[row["Latitude"],row["Longitude"]],
                radius = RADIUS,
                color="black",
                weight=1,
                fill_opacity=0.2,
                opacity=1,
                fill_color=formdata[f"colour{i}"].lower(),
                fill=False,  # gets overridden by fill_color
                tooltip=tooltip,
              ).add_to(m)
                  
    m.fit_bounds(m.get_bounds(), padding=(30, 30))

    folium.TileLayer('cartodbpositron').add_to(m)
    folium.TileLayer('openstreetmap').add_to(m)

    # Add the option to switch tiles
    folium.LayerControl().add_to(m)

    fs = plugins.Fullscreen().add_to(m)

    gc = plugins.Geocoder(collapsed=True, position='topleft', add_marker=True).add_to(m)

    mc = plugins.MeasureControl( position='topleft').add_to(m)
    
    return m


@app.route('/', methods=['POST', 'GET'])
def index():
  iframe = ""
  crunched = None  

  form = MapForm()
  #maprequest = request.args.get('m')
  #print ("maprequest", maprequest)
  if request.method == 'POST':# or ( maprequest):
    
    if (request.form['password'] != app.secret_key):
      error = ("Password Didn't Match")
      return render_template("index.html", form=request.form, error=error, crunch=None)
    
    formdata = {}

    for i in range(1,4):
      formdata[f'points{i}']    = request.form[f'points{i}']
      formdata[f'colour{i}']    = request.form[f'colour{i}']
      formdata[f'icon{i}']      = request.form[f'icon{i}']
      formdata[f'label{i}']     = request.form[f'label{i}']
      formdata[f'postcode{i}']  = request.form[f'postcode{i}']
      formdata[f'renderer{i}']  = request.form[f'renderer{i}']
    
    m = get_map(formdata)

    if "submit" in request.form:
       return m.get_root()._repr_html_()

    # set the iframe width and height
    m.get_root().width = "800px"
    m.get_root().height = "600px"
    iframe = m.get_root()._repr_html_()
    
    crunched = urlsafe_b64encode(json.dumps(formdata).encode('utf-8')).decode("utf-8", "ignore")    
    #print(crunched)

  return render_template("index.html", form=form, iframe=iframe, crunched=crunched)


@app.route('/map/<map>', methods=['GET'])
def maprender(map):
  text = urlsafe_b64decode(map+ "====")
  data = json.loads(text)
  m = get_map(data)
  return m.get_root()._repr_html_()
  

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
