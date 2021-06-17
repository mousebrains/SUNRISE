"""Classes and functions for writing kml and kmz files

Some classes to write kml and kmz files with a limited subset of KML elements.
Should run with python 3.6 or later (tested on python 3.9.4) or earlier
versions if you change out the f-strings.
Module Dependencies:
    os
    numpy
    matplotlib
    datetime
    zipfile
Written May 2021 by Jamie Hilditch for SUNRISE 2021 Cruise
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba, to_hex
from datetime import datetime
from zipfile import ZipFile

class Writer():
    """Base for writing a kml file

    Arguments:
    xml_header: str, optional -- default '<?xml version="1.0" encoding="UTF-8"?>'
        sets the xml tag at the top of the kml document
    KML_namespace: str, optional -- default '<kml xmlns="http://www.opengis.net/kml/2.2">'
        sets the kml tag at the top of the kml document
    """

    def __init__(self,xml_header=None,KML_namespace=None):
        self.children = []
        if xml_header is None:
            self.xml_header = '<?xml version="1.0" encoding="UTF-8"?>'
        else:
            self.xml_header = str(xml_header)
        if KML_namespace is None:
            self.KML_namespace = '<kml xmlns="http://www.opengis.net/kml/2.2">'
        else:
            self.KML_namespace = str(KML_namespace)

    def write_to_file(self,file_object):
        """Writes a kml file

        Writes the xml, kml, and Document tags. Then calls the write_to_file
        method on all the child elements. Then closes the Document and kml tags.

        Arguments:
        file_object: file object
            kml file open for writing

        Returns:
        None
        """

        file_object.write(self.xml_header)
        file_object.write("\n")
        file_object.write(self.KML_namespace)
        file_object.write("\n\t<Document>\n")
        for child in self.children:
            child.write_to_file(file_object,indent=2)
        file_object.write("\t</Document>\n")
        file_object.write("</kml>")

    def append(self,object):
        """Shorthand for self.children.append"""
        self.children.append(object)

class Folder():
    """Create a folder for a kml file

    Arguments:
    name: str
        name of the folder, appears in the places panel
    """

    def __init__(self,name):
        self.children = []
        self.name = name

    def write_to_file(self,file_object,indent=0):
        """Writes the folder tags and child elements to a kml file

        Writes the Folder and name tags before calling write_to_file on the
        child elements and closing the Folder tag.

        Arguments:
        file_object: file object
            kml file open for writing
        indent: int, optional -- default 0
            sets the indent level of the Folder tag

        Returns:
        None
        """

        file_object.write("\t"*indent + "<Folder>\n")
        file_object.write("\t"*(indent+1) + "<name>" + self.name + "</name>\n")
        for child in self.children:
            child.write_to_file(file_object,indent=indent+1)
        file_object.write("\t"*indent + "</Folder>\n")

    def append(self,object):
        """Shorthand for self.children.append"""
        self.children.append(object)

class Style():
    """Create a kml Style Element

    Individual style elements (IconStyle, LabelStyle etc) are provided as
    dictionaries where the keys are kml tags and the values are the
    property values.
    e.g. Line={"width": 2} will add a line in the LineStyle element:
        <width>2</width>
    Icon if provided must have a key "href" with the filepath to the icon
    image

    Arguments:
    id: str
        The id of the Style. Used by other elements as the a styleUrl #id
    Icon: dic, optional
        dictionary containing key value pairs defining the IconStyle elements
        must include the "href" key
    Label: dic, optional
        dictionary containing key value pairs defining the LabelStyle elements
    Line: dic, optional
        dictionary containing key value pairs defining the LineStyle elements
    Poly: dic, optional
        dictionary containing key value pairs defining the PolyStyle elements
    Balloon: dic, optional
        dictionary containing key value pairs defining the BalloonStyle elements
    List: dic, optional
        dictionary containing key value pairs defining the ListStyle elements
    """

    def __init__(self,id,Icon=None,Label=None,Line=None,Poly=None,Balloon=None,List=None):
        self.id = id
        self.Icon = Icon
        self.Label = Label
        self.Line = Line
        self.Poly = Poly
        self.Balloon = Balloon
        self.List = List

    def write_to_file(self,file_object,indent=0):
        """Writes a Style to a kml file

        Writes the Style tags and individual Style elements

        Arguments:
        file_object: file object
            kml file open for writing
        indent: int, optional -- default 0
            sets the indent level of the Style tag

        Returns:
        None
        """

        file_object.write("\t"*indent + "<Style id=\"" + self.id + "\">\n")
        if self.Icon is not None:
            file_object.write("\t"*(indent+1) + "<IconStyle>\n")
            file_object.write("\t"*(indent+2) + "<Icon>\n")
            file_object.write("\t"*(indent+3) + "<href>" + self.Icon.pop("href"," ") + "</href>\n")
            file_object.write("\t"*(indent+2) + "</Icon>\n")
            for key in self.Icon:
                file_object.write("\t"*(indent+2) + "<" + key + ">" + str(self.Icon[key]) + "</" + key + ">\n")
            file_object.write("\t"*(indent+1) + "</IconStyle>\n")
        if self.Label is not None:
            file_object.write("\t"*(indent+1) + "<LabelStyle>\n")
            for key in self.Label:
                file_object.write("\t"*(indent+2) + "<" + key + ">" + str(self.Label[key]) + "</" + key + ">\n")
            file_object.write("\t"*(indent+1) + "</LabelStyle>\n")
        if self.Line is not None:
            file_object.write("\t"*(indent+1) + "<LineStyle>\n")
            for key in self.Line:
                file_object.write("\t"*(indent+2) + "<" + key + ">" + str(self.Line[key]) + "</" + key + ">\n")
            file_object.write("\t"*(indent+1) + "</LineStyle>\n")
        if self.Poly is not None:
            file_object.write("\t"*(indent+1) + "<PolyStyle>\n")
            for key in self.Poly:
                file_object.write("\t"*(indent+2) + "<" + key + ">" + str(self.Poly[key]) + "</" + key + ">\n")
            file_object.write("\t"*(indent+1) + "</PolyStyle>\n")
        if self.Balloon is not None:
            file_object.write("\t"*(indent+1) + "<BalloonStyle>\n")
            for key in self.Balloon:
                file_object.write("\t"*(indent+2) + "<" + key + ">" + str(self.Balloon[key]) + "</" + key + ">\n")
            file_object.write("\t"*(indent+1) + "</BalloonStyle>\n")
        if self.List is not None:
            file_object.write("\t"*(indent+1) + "<ListStyle>\n")
            for key in self.List:
                file_object.write("\t"*(indent+2) + "<" + key + ">" + str(self.List[key]) + "</" + key + ">\n")
            file_object.write("\t"*(indent+1) + "</ListStyle>\n")
        file_object.write("\t"*(indent) + "</Style>\n")

class LineString():
    """Class for creating and writing a kml linestring

    Arguments:
    coordinates: tuple or list
                 containing iterable coordinate pairs (lon,lat) or
                 triples (lon,lat,alt)

    Keyword Arguments:
    name: str
        The name of the line. Displayed in the places panel in Google
        Earth.
    TimeSpan: tuple or list
        (begin,end) where begin and end are datetime objects with timezone
        information
    TimeStamp: datetime
        datetime object with timezone information
    description: str
        Description of the line. Appears in the balloon in Google Earth
    altitudeMode: str
        required if altitude data is given in coordinates
        > "relativeToGround" -- from the surface of the Earth
        > "absolute" -- above sea level
        > "relativeToSeaFloor" -- from the bottom of major bodies of water
    color: str
        sets the line color style. hex in the order #aabbggrr
    width: int or str
        sets the line width style
    styleUrl: str
        the url id of a style element
    ExtendedData: dict
        extra data to include as name, value pairs
    """

    def __init__(self,coordinates,**kwargs):
        self.coordinates = coordinates
        self.name = kwargs.pop("name",None)
        self.TimeSpan = kwargs.pop("TimeSpan",None)
        self.TimeStamp = kwargs.pop("TimeStamp",None)
        self.description = kwargs.pop("description",None)
        self.altitudeMode = kwargs.pop("altitudeMode",None)
        self.color = kwargs.pop("color",None)
        self.width = kwargs.pop("width",None)
        self.styleUrl = kwargs.pop("styleUrl",None)
        self.ExtendedData = kwargs.pop("ExtendedData",{})

        for key in kwargs:
            print(f"{key} is not a valid input")

    def write_to_file(self,file_object,indent=0):
        """Writes the linestring to a kml file

        Arguments:
        file_object: file object
            kml file opened for writing or appending
        indent: int, optional
            sets the indentation level in the kml file for easy reading

        Returns:
        None
        """

        file_object.write("\t"*indent + "<Placemark>\n")

        if self.name is not None:
            file_object.write("\t"*(indent+1) + "<name>" + self.name + "</name>\n")
        if self.styleUrl is not None:
            file_object.write("\t"*(indent+1) + "<styleUrl>" + self.styleUrl + "</styleUrl>\n")
        if self.TimeSpan is not None:
            file_object.write("\t"*(indent+1) + "<TimeSpan>\n")
            file_object.write("\t"*(indent+2) + "<begin>" + self.TimeSpan[0].isoformat() + "</begin>\n")
            file_object.write("\t"*(indent+2) + "<end>" + self.TimeSpan[1].isoformat() + "</end>\n")
            file_object.write("\t"*(indent+1) + "</TimeSpan>\n")
        if self.TimeStamp is not None:
            file_object.write("\t"*(indent+1) + "<TimeStamp>\n")
            file_object.write("\t"*(indent+2) + "<when>" + self.TimeStamp.isoformat() + "</when>\n")
            file_object.write("\t"*(indent+1) + "</TimeStamp>\n")
        if self.description is not None:
            file_object.write("\t"*(indent+1) + "<description>" + self.description + "</description>\n")
        if self.ExtendedData:
            file_object.write("\t"*(indent+1) + "<ExtendedData>\n")
            file_object.write("\t"*(indent+2) + "<SchemaData schemaUrl=\"#" +
                self.ExtendedData.pop("schemaUrl") + "\">\n")
            for key in self.ExtendedData:
                file_object.write("\t"*(indent+3) + "<SimpleData name=\"" + key + "\">" +
                    str(self.ExtendedData[key]) + "</SimpleData>\n")
            file_object.write("\t"*(indent+2) + "</SchemaData>\n")
            file_object.write("\t"*(indent+1) + "</ExtendedData>\n")
        file_object.write("\t"*(indent+1) + "<LineString>\n")
        file_object.write("\t"*(indent+2) + "<coordinates>\n")
        for coords in self.coordinates:
            file_object.write("\t"*(indent+3) + f"{coords[0]:f},{coords[1]:f}")
            if len(coords) == 3:
                file_object.write(f",{coords[2]:f}\n")
            else:
                file_object.write("\n")
        file_object.write("\t"*(indent+2) + "</coordinates>\n")
        if self.altitudeMode is not None:
            file_object.write("\t"*(indent+2) + "<altitudeMode>" + self.altitudeMode + "</altitudeMode>\n")
        file_object.write("\t"*(indent+1) + "</LineString>\n")

        if (self.color is not None) or (self.width is not None):
            file_object.write("\t"*(indent+1) + "<Style>\n")
            file_object.write("\t"*(indent+2) + "<LineStyle>\n")
            if self.color is not None:
                file_object.write("\t"*(indent+3) + "<color>" + self.color + "</color>\n")
            if self.width is not None:
                file_object.write("\t"*(indent+3) + "<width>" + str(self.width) + "</width>\n")
            file_object.write("\t"*(indent+2) + "</LineStyle>\n")
            file_object.write("\t"*(indent+1) + "</Style>\n")

        file_object.write("\t"*indent + "</Placemark>\n")

class ScreenOverlay():
    """Class for creating and writing a kml ScreenOverlay

    Arguments:
    href: str
        relative link from folder containing the kml file to the image to be
        overlayed
    overlayXY: tuple -- default (1,1)

    screenXY: tuple -- default (0.95,0.95)

    size: tuple -- default (0.25,0.1)

    rotationXY: tuple -- default(0,0)

    visibility: int or str

    units: str -- default "fraction"
    > "fraction" --
    > "pixels" --
    name: str, optional
        name of the screen overlay. Appears in the places panel in Google
        Earth
    """

    def __init__(self,href,overlayXY=(1,1),screenXY=(0.95,0.95),size=(0.25,0.1),rotationXY=(0,0),visibility=0,units="fraction",name=None):
        self.href = href
        self.overlayXY = {'x': overlayXY[0],
            'y': overlayXY[1],
            'xunits': units,
            'yunits': units}
        self.screenXY = {'x': screenXY[0],
            'y': screenXY[1],
            'xunits': units,
            'yunits': units}
        self.size = {'x': size[0],
            'y': size[1],
            'xunits': units,
            'yunits': units}
        self.rotationXY = {'x': rotationXY[0],
            'y': rotationXY[1],
            'xunits': units,
            'yunits': units}
        self.visibility = visibility
        self.name = name

    def write_to_file(self,file_object,indent=0):

        file_object.write("\t"*indent + "<ScreenOverlay>\n")

        if self.name is not None:
            file_object.write("\t"*(indent+1) + "<name>" + self.name + "</name>\n")

        file_object.write("\t"*(indent+1) + "<Icon>\n")
        file_object.write("\t"*(indent+2) + "<href>" + self.href + "</href>\n")
        file_object.write("\t"*(indent+1) + "</Icon>\n")
        file_object.write("\t"*(indent+1) + f"<overlayXY x=\"{self.overlayXY['x']}\" y=\"{self.overlayXY['y']}\" "
            f"xunits=\"{self.overlayXY['xunits']}\" yunits=\"{self.overlayXY['yunits']}\"/>\n")
        file_object.write("\t"*(indent+1) + f"<screenXY x=\"{self.screenXY['x']}\" y=\"{self.screenXY['y']}\" "
            f"xunits=\"{self.screenXY['xunits']}\" yunits=\"{self.screenXY['yunits']}\"/>\n")
        file_object.write("\t"*(indent+1) + f"<rotationXY x=\"{self.rotationXY['x']}\" y=\"{self.rotationXY['y']}\" "
            f"xunits=\"{self.rotationXY['xunits']}\" yunits=\"{self.rotationXY['yunits']}\"/>\n")
        file_object.write("\t"*(indent+1) + f"<size x=\"{self.size['x']}\" y=\"{self.size['y']}\" "
            f"xunits=\"{self.size['xunits']}\" yunits=\"{self.size['yunits']}\"/>\n")
        file_object.write("\t"*(indent+1) + "<visibility>" + str(self.visibility) + "</visibility>\n")

        file_object.write("\t"*(indent) + "</ScreenOverlay>\n")

class Point():
    """Create a kml Point Element

    Arguments:
    lon: float, str
        longitude of the point
    lat: float, str
        latitude of the point

    Keyword Arguments:
    alt: float, str
        Set the value of the point's altitude
    name: str
        The name of the line. Displayed in the places panel in Google
        Earth.
    TimeSpan: tuple or list
        (begin,end) where begin and end are datetime objects with timezone
        information
    TimeStamp: datetime
        datetime object with timezone information
    description: str
        Description of the line. Appears in the balloon in Google Earth
    altitudeMode: str
        required if altitude data is given in coordinates
        > "relativeToGround" -- from the surface of the Earth
        > "absolute" -- above sea level
        > "relativeToSeaFloor" -- from the bottom of major bodies of water
    styleUrl: str
        the url id of a style element
    href: str
        adds an icon using the image at this file path
    """

    def __init__(self,lon,lat,**kwargs):
        self.lon = lon
        self.lat = lat
        self.alt = kwargs.pop('alt',None)
        self.altitudeMode = kwargs.pop('altitudeMode',None)
        self.TimeSpan = kwargs.pop("TimeSpan",None)
        self.TimeStamp = kwargs.pop("TimeStamp",None)
        self.styleUrl = kwargs.pop("styleUrl",None)
        self.href = kwargs.pop("href",None)
        self.name = kwargs.pop("name",None)
        self.description = kwargs.pop("description",None)

    def write_to_file(self,file_object,indent=0):
        """Writes the Point to a kml file

        Arguments:
        file_object: file object
            kml file opened for writing or appending
        indent: int, optional
            sets the indentation level in the kml file for easy reading

        Returns:
        None
        """

        file_object.write("\t"*indent + "<Placemark>\n")

        if self.name is not None:
            file_object.write("\t"*(indent+1) + "<name>" + self.name + "</name>\n")
        if self.styleUrl is not None:
            file_object.write("\t"*(indent+1) + "<styleUrl>" + self.styleUrl + "</styleUrl>\n")
        if self.href is not None:
            file_object.write("\t"*(indent+1) + "<Style>\n")
            file_object.write("\t"*(indent+2) + "<IconStyle>\n")
            file_object.write("\t"*(indent+3) + "<Icon>\n")
            file_object.write("\t"*(indent+4) + "<href>" + self.href + "</href>\n")
            file_object.write("\t"*(indent+3) + "</Icon>\n")
            file_object.write("\t"*(indent+2) + "</IconStyle>\n")
            file_object.write("\t"*(indent+1) + "</Style>\n")
        if self.TimeSpan is not None:
            file_object.write("\t"*(indent+1) + "<TimeSpan>\n")
            file_object.write("\t"*(indent+2) + "<begin>" + self.TimeSpan[0].isoformat() + "</begin>\n")
            file_object.write("\t"*(indent+2) + "<end>" + self.TimeSpan[1].isoformat() + "</end>\n")
            file_object.write("\t"*(indent+1) + "</TimeSpan>\n")
        if self.TimeStamp is not None:
            file_object.write("\t"*(indent+1) + "<TimeStamp>\n")
            file_object.write("\t"*(indent+2) + "<when>" + self.TimeStamp.isoformat() + "</when>\n")
            file_object.write("\t"*(indent+1) + "</TimeStamp>\n")
        if self.description is not None:
            file_object.write("\t"*(indent+1) + "<description>" + self.description + "</description>\n")

        file_object.write("\t"*(indent+1) + "<Point>\n")
        file_object.write("\t"*(indent+2) + "<coordinates>")
        file_object.write(str(self.lon) + "," + str(self.lat))
        if self.alt is not None:
            file_object.write("," + str(alt))
        file_object.write("</coordinates>\n")
        if self.altitudeMode is not None:
            file_object.write("\t"*(indent+2) + "<altitudeMode>" + self.altitudeMode + "</altitudeMode>\n")
        file_object.write("\t"*(indent+1) + "</Point>\n")
        file_object.write("\t"*indent + "</Placemark>\n")

class Schema():

    def __init__(self,name,id,*args):
        self.name = name
        self.id = id
        self.fields = list(args)

    def write_to_file(self,file_object,indent=0):
        file_object.write("\t"*indent + "<Schema name=\"" + self.name + "\" id=\"" + self.id + "\">\n")
        for field in self.fields:
            file_object.write("\t"*(indent+1) + "<SimpleField type=\"" + field["type"] +
                "\" name=\"" + field["name"] + "\">\n")
            file_object.write("\t"*(indent+2) + " <displayName><![CDATA[" + field["name"] + "]]></displayName>\n")
            file_object.write("\t"*(indent+1) + "</SimpleField>\n")
        file_object.write("\t"*indent + "</Schema>\n")

def kml_hex(color):
    """Convert matplotlib color to kml hex

    Arguments:
    color: matplotlib color
        Matplotlib recognizes the following formats to specify a color:
        > an RGB or RGBA (red, green, blue, alpha) tuple of float values in closed
        interval [0, 1] (e.g., (0.1, 0.2, 0.5) or (0.1, 0.2, 0.5, 0.3));
        > a hex RGB or RGBA string (e.g., '#0f0f0f' or '#0f0f0f80'; case-insensitive);
        > a shorthand hex RGB or RGBA string, equivalent to the hex RGB or RGBA string
        obtained by duplicating each character, (e.g., '#abc', equivalent to '#aabbcc',
        or '#abcd', equivalent to '#aabbccdd'; case-insensitive);
        > a string representation of a float value in [0, 1] inclusive for gray
        level (e.g., '0.5');
        > one of the characters {'b', 'g', 'r', 'c', 'm', 'y', 'k', 'w'}, which are
        short-hand notations for shades of blue, green, red, cyan, magenta, yellow,
        black, and white. Note that the colors 'g', 'c', 'm', 'y' do not coincide
        with the X11/CSS4 colors. Their particular shades were chosen for better
        visibility of colored lines against typical backgrounds.
        > a X11/CSS4 color name (case-insensitive);
        > a name from the xkcd color survey, prefixed with 'xkcd:' (e.g., 'xkcd:sky blue';
        case insensitive);
        > one of the Tableau Colors from the 'T10' categorical palette (the default
        color cycle): {'tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple',
        'tab:brown', 'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan'} (case-insensitive);
        > a "CN" color spec, i.e. 'C' followed by a number, which is an index into
        the default property cycle (rcParams["axes.prop_cycle"] (default: cycler('color',
         ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2',
         '#7f7f7f', '#bcbd22', '#17becf']))); the indexing is intended to occur at
         rendering time, and defaults to black if the cycle does not include color.

    Returns: str
        color string in kml hex format "aabbggrr"
    """

    r,g,b,a = to_rgba(color)
    hex_color = f"{int(a*255):02x}{int(b*255):02x}{int(g*255):02x}{int(r*255):02x}"
    return hex_color

def kml_coloured_line(directory,filename,data,data_key,lon,lat,times,cmap,label,dmin=None,dmax=None):
    """Make a kmz file with a line coloured by data

    This creates a series of line segments coloured using a colormap. The
    colour bar is implemented in Google Earth as a screen overlay so its
    position is fixed. In order to be able to display multiple colour bars
    the kml file contains 8 colour bar overlays which are by default toggled
    off.

    Arguments:
    directory: path-like object
        path to the directory in which to save the kmz file
    filename: str
        name of the kmz file without .kmz file extension
        - this function also creates filename.png and filename.kml
        that get zipped up into filename.kmz and then deleted
    data: dictionary
        data to include e.g. salinity, temperature
    data_key: str
        key of data to colour the line
    lon: list/array
        longitudes of the data points
    lat: list/array
        latitudes of the data points
    times: list
        list of datetime objects with timezone info
    cmap: colormap
        colormap used to colour the data
    label: str
        title of the colour bar
    dmin: float, optional
        minimum of the colour map if not given use minimum of data
    dmax: float, optional
        maximum of the colour map if not given use maximum of data

    Returns:
        None
    """

    # Check key is valid and we have data
    if (data_key not in data):
        return None

    if len(data[data_key]) == 0:
        return None

    base = Writer()

    if dmin is None:
        dmin = np.nanmin(data[data_key])
    if dmax is None:
        dmax = np.nanmax(data[data_key])

    # first scale the data
    colour_data = [(d - dmin)/(dmax - dmin) for d in data[data_key]]

    # make the lines
    lines_folder = Folder("lines")
    schema = Schema("Data", "Data",
        {"name": "Latitude", "type": "float"},
        {"name": "Longitude", "type": "float"},
        {"name": "Time", "type": "string"})
    for key in data:
        schema.fields.append({"name": key, "type": "float"})
    base.children.append(schema)
    base.children.append(lines_folder)
    for i in range(len(times)-1):
        coords = [(lon[i],lat[i]),(lon[i+1],lat[i+1])]
        TimeSpan = (times[i],times[i+1])
        width = 5
        #r,g,b,a = cmap((data[i] + data[i+1])/2)
        color = kml_hex(cmap((colour_data[i] + colour_data[i+1])/2))
        ExtendedData = {
            "schemaUrl": "Data",
            "Time": times[i].strftime("%d-%b %H:%M"),
            "Latitude": f"{lat[i]:.3f}",
            "Longitude": f"{lon[i]:.3f}",
            }
        for key in data:
            ExtendedData[key] = f"{data[key][i]:.3f}"
        lines_folder.children.append(LineString(
            coords,
            TimeSpan=TimeSpan,
            width=width,
            color=color,
            ExtendedData=ExtendedData
        ))

    # Now make a colour bar
    a = [[dmin,dmax]]
    plt.figure(figsize=(9, 1))
    img = plt.imshow(a, cmap=cmap)
    plt.gca().set_visible(False)
    cax = plt.axes([0.1, 0.4, 0.8, 0.2])
    cb = plt.colorbar(orientation='horizontal', cax=cax)
    cb.ax.tick_params(labelsize=18)
    cax.set_title(label,fontsize=18)
    plt.savefig(os.path.join(directory,filename + ".png"))
    plt.close()

    colourbar_folder = Folder("colorbars")
    base.children.append(colourbar_folder)
    for i in range(8):
        colourbar_folder.children.append(ScreenOverlay(
            filename + ".png",
            screenXY=(0.95,0.95-0.1*i),
            name=f"CB{i+1}_{label}"
        ))

    # Write kml file
    with open(os.path.join(directory,filename + ".kml") ,'w') as f:
        base.write_to_file(f)

    # Zip into kmz
    zp = ZipFile(os.path.join(directory,filename + ".kmz"),'w')
    zp.write(os.path.join(directory,filename + ".kml"),filename + ".kml")
    zp.write(os.path.join(directory,filename + ".png"),filename + ".png")
    zp.close()

    # Tidy up
    os.remove(os.path.join(directory,filename + ".png"))
    os.remove(os.path.join(directory,filename + ".kml"))

def kml_vectors(directory,filename,lon,lat,east,north,times,folders=None,color="k",vmax=1/20,dmax=None,compress=True):
    """Display vector data

    Turn vector data into a kml or kmz file e.g. ADCP data. Can handle multiple
    depths by inputting 2D arrays into east and north and specifying a list of
    folder names and colors for the different depths.

    Arguments:
    directory: path-like object
        directory of file
    filename: str
        filename without .kml or .kmz extension
    lon: list/array
        1D list or array of longitudes
    lat: list/array
        1D list or array of latitudes
    east: numpy array
        East velocities - if 2D [time,depth]
    north: numpy array
        North velocities - if 2D [time,depth]
    times: list
        1D list of datetimes of the data points with timezone info
    folders: list, optional
        list of folder names - one for each depth
        optional if only plotting one depth
    color: matplotlib color or list, optional
        a matplotlib color or list of colors one for each depth if using 2D array
        optional if plotting one depth - defaults to black in this case
    vmax: float -- default 0.05
        maximum length of vector in degrees latitude
    dmax: float, optional
        maximum value of the velocity data for normalisation
        defaults to maximum length of data
    compress: boolean -- default True
        if True compresses the kml to a kmz

    Returns:
    None
    """

    base = Writer()

     # Conversion factor from nm to minutes of longitude at 30N
    conv = 96.5/110.9

    if dmax is None:
        lengths = (np.array(north)**2 + conv**2*np.array(east)**2)**0.5
        dmax = np.amax(lengths)
        if dmax == 0:
            dmax = 1

    if folders is None:
        vectors_folder = Folder(filename)
        base.children.append(vectors_folder)
        for i in range(len(times)):
            coords = [(lon[i],lat[i]), (lon[i]+east[i]*vmax/dmax*conv,
                lat[i]+north[i]*vmax/dmax)]
            TimeStamp = times[i]
            # r,g,b,a = to_rgba(color)
            hex_color = kml_hex(color)
            vectors_folder.children.append(LineString(
                coords,
                TimeStamp=TimeStamp,
                color=hex_color,
                width=1
            ))
    else:
        if (len(folders) == east.shape[1]) and (len(folders) == north.shape[1]):
            for j in range(len(folders)):
                vectors_folder = Folder(folders[j])
                base.children.append(vectors_folder)
                for i in range(len(times)):
                    coords = [(lon[i],lat[i]), (lon[i]+east[i][j]*vmax/dmax*conv,
                        lat[i]+north[i][j]*vmax/dmax)]
                    TimeStamp = times[i]
                    # r,g,b,a = to_rgba(color[j])
                    hex_color = kml_hex(color[j])
                    vectors_folder.children.append(LineString(
                        coords,
                        TimeStamp = TimeStamp,
                        color=hex_color,
                        width=1
                    ))

    with open(os.path.join(directory,filename + ".kml"),'w') as f:
        base.write_to_file(f)

    if compress:
        zp = ZipFile(os.path.join(directory,filename + ".kmz"),'w')
        zp.write(os.path.join(directory,filename + ".kml"),filename + ".kml")
        zp.close()

        # Tidy up
        os.remove(os.path.join(directory,filename + ".kml"))

def kml_path(directory,filename,lon,lat,times,color="k",width=1,iconpath=None,iconscale=1,name=None,labelscale=0):
    """Display asset path

    e.g. plotting ship track
    Plots lines showing the asset path and then optionally adds an icon at the
    last data point (e.g. for the current location)

    Arguments:
    directory: path-like object
        path to the directory in which to save the kmz file
    filename: str
        name of the kmz file without .kmz file extension
        - this function also creates filename.kml
        that get zipped up into filename.kmz and then deleted
    lon: list/array
        longitudes of the data points
    lat: list/array
        latitudes of the data points
    times: list
        list of datetime objects with timezone info
    color: matplotlib color, optional -- default "k" > black
        color of the lines
    width: int, str, optional -- default 1
        width of the lines
    iconpath: path-like object, optional
        adds an icon at the end of the path
    iconscale: float, str, optional -- default 1
        sets the icon size
    name: str, optional -- default filename
        label of the icon
    labelscale: float, str, optional -- default 0
        sets the icon label size

    Returns:
    None
    """

    base = Writer()

    line_style = Style("lines",Line={
        "color": kml_hex("k"),
        "width": width
    })
    base.children.append(line_style)

    if iconpath is not None:
        point_style = Style("point",Icon={
            "href": "icon.png",
            "scale": iconscale
        },
        Label={
            "scale": labelscale
        })
        base.children.append(point_style)

    # make the lines
    lines_folder = Folder("lines")
    base.children.append(lines_folder)
    for i in range(len(times)-1):
        coords = [(lon[i],lat[i]),(lon[i+1],lat[i+1])]
        TimeSpan = (times[i],times[i+1])
        lines_folder.children.append(LineString(
            coords,
            TimeSpan=TimeSpan,
            styleUrl="#lines"
        ))

    #icon
    if iconpath is not None:
        if name is not None:
            icon_name = name
        else:
            icon_name = filename
        end_point = Point(lon[-1], lat[-1],
            TimeStamp=times[-1],
            styleUrl="#point",
            name=icon_name,
            description=times[-1].isoformat())
        base.children.append(end_point)

    # Write kml file
    with open(os.path.join(directory,filename + ".kml") ,'w') as f:
        base.write_to_file(f)

    # Zip into kmz
    zp = ZipFile(os.path.join(directory,filename + ".kmz"),'w')
    zp.write(os.path.join(directory,filename + ".kml"),filename + ".kml")
    zp.write(iconpath,"icon.png")
    zp.close()

    # Tidy up
    os.remove(os.path.join(directory,filename + ".kml"))

if __name__ == "__main__":
    pass
    # import cmocean.cm as cmo
    # from datetime import timezone

    # longitudes = np.linspace(-92.85,-92.9,20)
    # latitudes = np.append(np.linspace(28.5,28.7,10),np.linspace(28.7,28.5,10))
    # times = ["2020-04-22T" + str(10 + n//3) + ":" + f"{20*n%3:02d}" + ":00-07:00" for n in range(20)]
    # times = [datetime.fromisoformat(time) for time in times]
    # salinity = np.append(np.linspace(31,29,10),np.linspace(29,30.8,10))
    # north = np.linspace(0.05,0.06,20)
    # east = np.append(np.linspace(-0.2,-0.4,5),np.linspace(-0.4,-0.3,5))
    # east = np.append(east,east[::-1])
    #
    # kml_coloured_line(r".",
    #     "salinity",
    #     salinity,
    #     longitudes,
    #     latitudes,
    #     times,
    #     cmo.deep,
    #     "Salinity")
    #
    # kml_vectors(r".",
    # "ADCP",
    # longitudes,
    # latitudes,
    # east,
    # north,
    # times,
    # color="r",
    # compress=True
    # )

    # kml_path(r".",
    # "path",
    # longitudes,
    # latitudes,
    # times,
    # iconpath=r"..\icons\armstrong.png",
    # name="Ship Track")
