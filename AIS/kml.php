<?php
// Read in CSV files for the drifters and generate a KML file with their recent tracks

header("Content-Type: application/xml");


function loadJSON(string $fn, array $known) {
	if (($fp = fopen($fn, "r")) === FALSE) return []; // Open failed
    $ships = [];
	while (($jline = fgets($fp)) !== FALSE) { // Read until EOF
		$iT = Null;
		$iId = Null;
		$iLat = Null;
		$iLon = Null;
		$iName = Null;
		$isog = Null;
		$icog = Null;
		$fields = json_decode($jline, TRUE);
		$iId = $fields['mmsi'];
		#Not sure this is totally necessary
		if(array_key_exists($iId, $ships))
			$varT = "T";
		else
			$varT = "T0";

		#also not sure if this is necessary
        if(isset($fields['utc_hour']) && isset($fields['timestamp'])) {
			if($fields['utc_hour'] > date("H")) {
				#if a timestamp is given from the future, it must be from the previous day.
				$today = substr(date("c", mktime(0, 0, 0, date("m"), date("d")-1, date("Y"))), 0, 10);
				$iT = $today . "T" . $fields['utc_hour'] .":". $fields['utc_min'].":". $fields['timestamp']."Z";
			} else {
            	$iT = date("Y-m-d"). "T" . $fields['utc_hour'] .":". $fields['utc_min'].":". $fields['timestamp']."Z";
			}
		} else {
			$iT = date("Y-m-d") . "T" . date("H:i:s") . "Z";
		}

		if(array_key_exists('y', $fields) && array_key_exists('x', $fields)){
			$iLat = $fields['y'];
			$iLon = $fields['x'];
		}
		if(array_key_exists($iId, $known)){
			$iName = $known[$iId];
		} else {
			if(array_key_exists('name', $fields)) {
				$iName = $fields['name'];
			}
		}
		if(array_key_exists('sog', $fields))
			$isog = $fields['sog'];
		if(array_key_exists('cog', $fields))
			$icog = $fields['cog'];
		$attributes = array($iT, $iLat, $iLon, $iId, $iName, $isog, $icog);
		if(!array_key_exists($iId, $ships)) {
			$ships[$iId] = [];
		} 
		array_push($ships[$iId], $attributes);
    }
	fclose($fp); // Close the file and free resources
	return $ships;
}
$known = array(367020910=>"WS", 367652000=>"PEL", 338336647=>"ROSS1", 338336648=>"ROSS2", 338401292=>"AUTORESEARCH1", 995541771=> "WW1", 995541777=> "WW2");


$ships = loadJSON("ais.json", $known);


// construct the hostname for inserting into the icon style href
$URLprefix = $_SERVER["REQUEST_SCHEME"] . "://" . $_SERVER["HTTP_HOST"];

// Now spit out KML via the XMLWriter

$r = new XMLWriter();
$r->openMemory(); // Build in memory
$r->startDocument("1.0", "UTF-8"); // XML type
$r->startElement("kml"); // Start a kml stanza
$r->writeAttribute("xmlns", "http://www.opengis.net/kml/2.2");
$r->writeAttribute("xmlns:gx", "http://www.google.com/kml/ext/2.2");
$r->startElement("Document");
$r->startElement("Style");
$r->writeAttribute("id",  "drifterStyle");
$r->startElement("LabelStyle");
$r->writeElement("scale", .2);
$r->endElement(); //labelstyle
$r->startElement("IconStyle");
$r->writeElement("scale", .2);
$r->startElement("Icon");
$r->writeElement("href", $URLprefix . "/Shore/kml_code/icons/icon_ship.png");
#$r->startElement("LineStyle");
#$r->writeElement("color", "ffffffff");
#$r->writeElement("width", 10);
#$r->endElement(); //linestyle

$r->endElement();//icon
$r->endElement();//icon style
$r->endElement();//style
foreach ($ships as $id=>$ship) {
	$r->startElement("Placemark");

	$shipName = Null;
	$shipSpeed = Null;
	$shipCourse = Null;
	 
	foreach($ship as $s){
		if (!($s[4] === Null))
			$shipName = $s[4];	
		if(!($s[5] === Null))
			$shipSpeed = $s[5];
		if(!($s[6] === Null))
			$shipCourse = $s[6];
	}
	if(!($shipName === Null)) {
		$r->writeElement("name", $shipName);
		$r->startElement("ExtendedData");
		$r->startElement("Data");
		$r->writeAttribute("name", "mmsi");
		$r->writeElement("value", $id);
		$r->endElement(); //data
	} else {
		$r->writeElement("name", $id); 
    	$r->startElement("ExtendedData"); 
		$r->startElement("Data");
		$r->writeAttribute("name", "name");
		$r->writeElement("value", "Unidentified Vessel");
		$r->endElement(); //data
	}
	if(!($shipSpeed === Null)) {
		$r->startElement("Data");
		$r->writeAttribute("name", "sog");
		$r->writeElement("value", $shipSpeed);
		$r->endElement(); //data
	}
	if(!($shipCourse === Null)) {
		$r->startElement("Data")
		$r->writeAttribute("name", "cog");
		$r->writeElement("value", $shipCourse);
		$r->endElement(); //data
	}
	reset($ship);
    $r->endElement(); //extended data
	$r->startElement("gx:Track");
	#$r->writeAttribute("id", $id);
	
	$seen = [];
	foreach($ship as $s){
		if(!($s[0] === Null) and !($s[1] === Null) && !($s[2] === Null) && !array_key_exists($s[0], $seen)) {
        	$r->writeElement("when", $s[0]);
        	$r->writeElement("gx:coord", $s[2] . " " . $s[1] . " 0");
			array_push($seen, $s[0]); //file gets very large. trying to save space.
		}	
    }
	$r->endElement(); // gx:Track
	$r->endElement(); // PlaceMark
}
$r->endElement(); // kml
$r->endDocument(); // XML
echo $r->outputMemory(true); // Clean up and generate a string
?>
