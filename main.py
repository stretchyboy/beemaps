from flask import Flask, render_template, request, flash
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

from flask_wtf import FlaskForm, CSRFProtect
from wtforms import PasswordField, StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length

import demo_points

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

class MapForm(FlaskForm):
    renderer1 = SelectField('Marker1', choices=MARKERS, default="Heatmap", validators=[DataRequired()])
    colour1 = SelectField('Colour', choices=COLOURS, default="None", validators=[DataRequired()])
    icon1 = SelectField('Icon', choices=ICONS, validators=[DataRequired()])
    postcode1 = SelectField('Postcode in Label', choices=YESNO, validators=[DataRequired(), ])
    label1 = SelectField('Label always on', choices=YESNO, validators=[DataRequired(), ])
    points1 = TextAreaField("Points", 
                            description='"Latitude, Longitude /Postcode (,Label)" can use tabs instead of ",", Must include header row',
                            validators=[DataRequired()])

    renderer2 = SelectField('Marker2', choices=MARKERS, default="Pins", validators=[DataRequired()])
    colour2 = SelectField('Colour', choices=COLOURS, default="Blue", validators=[DataRequired()])
    icon2 = SelectField('Icon', choices=ICONS, default="OK", validators=[DataRequired()])
    postcode2 = SelectField('Postcode in Label', choices=YESNO, validators=[DataRequired(), ])
    label2 = SelectField('Label always on', choices=YESNO, validators=[DataRequired(), ])
    points2 = TextAreaField("Points", 
                            #description='"Latitude, Longitude /Postcode (,Label)" can use tabs instead of ",", Must include header row',
                            #validators=[DataRequired()]
                            )

    renderer3 = SelectField('Marker3', choices=MARKERS, default="Pins", validators=[DataRequired()])
    colour3 = SelectField('Colour', choices=COLOURS, default="Green", validators=[DataRequired()])
    icon3 = SelectField('Icon', choices=ICONS, default="Flag", validators=[DataRequired()])
    postcode3 = SelectField('Postcode in Label', choices=YESNO, validators=[DataRequired(), ])
    label3 = SelectField('Label always on', choices=YESNO, validators=[DataRequired(), ])
    points3 = TextAreaField("Points", 
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
    if postcode in postcodecache:
      latitude = postcodecache[postcode]["latitude"]
      longitude = postcodecache[postcode]["longitude"]
      print(postcode, "from cache")
      return latitude, longitude
    
    url = f"http://api.getthedata.com/postcode/{postcode}"
    req = requests.get(url)

    if req.json()["status"] == "match":
        results = req.json()["data"]
        latitude = results.get("latitude")
        longitude = results.get("longitude")
        postcodecache[postcode] = {
          "latitude":  latitude,
          "longitude" : longitude
        }
    
    else:
        latitude = None
        longitude = None

    return latitude, longitude

def get_columns(code):
    api_param = code
    return get_data(api_param)

def get_latlong(text):
    data = io.StringIO(text.replace("\t",","))
    #print("get_latlong text", text, "data", data)
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
    #print("get_latlong df", df)
    
    return df

@app.route('/', methods=['POST', 'GET'])
def index():
  form = MapForm()
  iframe = ""

  if request.method == 'POST':
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

    for i in range(1,4):
      #print("i",i )
      if request.form[f'points{i}']:
        #print("request.form", request.form)
        df = get_latlong(request.form[f'points{i}']) 
        #print("df", df)
        
        if (len(df) == 0):
           continue

        if request.form[f"renderer{i}"] == "Heatmap":
          heat_data = [[row["Latitude"],row["Longitude"]] for index, row in df.iterrows()]
          HeatMap(heat_data).add_to(m)
        
        else: 
          for index, row in df.iterrows():
            #print("row", row)
            texts = []

            if request.form[f"postcode{i}"] == "Yes" and "Postcode" in row:
            #if "Postcode" in request.form[f"renderer{i}"] and "Postcode" in row:
              texts.append(row['Postcode'])

            if "Label" in row:
              texts.append(row['Label'])

            tooltip = None
            #permanent = "Label" in request.form[f"renderer{i}"]
            
            print(f"label{i}",request.form[f"label{i}"])
            permanent = request.form[f"label{i}"] == "Yes"
            
            if len(texts):
              tooltip = folium.Tooltip( ": ".join(texts), permanent=permanent)

            if "Pin" in request.form[f"renderer{i}"]:
              folium.Marker( 
                location=[row["Latitude"],row["Longitude"]],
                tooltip = tooltip,
                icon=folium.Icon(
                  color=request.form[f"colour{i}"].lower(),
                  icon=request.form[f"icon{i}"].lower(),
                )).add_to( m )
            
            if "Range" in request.form[f"renderer{i}"]:
              if request.form[f"renderer{i}"] == "Range 500m":
                 RADIUS = 500
              if request.form[f"renderer{i}"] == "Range 750m":
                 RADIUS = 750
              if request.form[f"renderer{i}"] == "Range 1km":
                 RADIUS = 100
              folium.Circle(
                location=[row["Latitude"],row["Longitude"]],
                radius = RADIUS,
                color="black",
                weight=1,
                fill_opacity=0.2,
                opacity=1,
                fill_color=request.form[f"colour{i}"].lower(),
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

    if "submit" in request.form:
       return m.get_root()._repr_html_()

    # set the iframe width and height
    m.get_root().width = "800px"
    m.get_root().height = "600px"
    iframe = m.get_root()._repr_html_()
  
  return render_template("index.html", form=form, iframe=iframe)
  
if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
