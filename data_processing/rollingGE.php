<?php
// Rolling Google Earth items

header("Content-Type: application/xml");

function mkLink(XMLWriter $r, string $url, string $name=NULL, string $descrip=NULL) {
	$r->startElement("NetworkLink"); // Start the NetworkLink element
	if (!is_null($name)) $r->writeElement("name", $name);
	if (!is_null($descrip)) $r->writeElement("description", $descrip); 
	$r->startElement("Link"); // The link information
	$r->writeElement("href", $url); // Where the information is
	$r->endElement(); // end the Link
	$r->endElement(); // end the NetworkLink
}

// construct the hostname for prefixing the url
if (array_key_exists("REQUEST_SCHEME", $_SERVER) && array_key_exists("HTTP_HOST", $_SERVER)) {
	$prefix = $_SERVER["REQUEST_SCHEME"] . "://" . $_SERVER["HTTP_HOST"];
	$hostname = explode(".", $_SERVER["HTTP_HOST"])[0];
} else {
	$prefix = "https://glidervm3.ceoas.oregonstate.edu";
	$hostname = "UNKNOWN";
}

// spit out KML via the XMLWriter

$r = new XMLWriter();
$r->openMemory(); // Build in memory
$r->startDocument("1.0", "UTF-8"); // XML type
$r->startElement("kml"); // Start a kml stanza
$r->writeAttribute("xmlns", "http://www.opengis.net/kml/2.2");
$r->startElement("Document");
$r->writeElement("name", "SUNRISE (" . $hostname .")");

$r->startElement("Folder");
$r->writeElement("name", "Pelican");
$r->endElement(); // Folder

$r->startElement("Folder");
$r->writeElement("name", "Walton Smith");
$r->endElement(); // Folder

mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican_1200kHz_vector.kmz", "Pelican 1200kHz Vector");
mkLink($r, $prefix . "/Shore/Satellite_KML/kml.php", "Satellite Images");
mkLink($r, $prefix . "/Shore/TXLA_model_forecast_KML/kml.php", "TXLA Forecasts");
mkLink($r, $prefix . "/Shore/Charts_etc/isobaths.kmz", "isobaths");
mkLink($r, $prefix . "/Shore/Charts_etc/Oil Platforms.kmz", "Platforms");

$r->startElement("Folder");
$r->writeElement("name", "Corridors");
mkLink($r, $prefix . "/Shore/Charts_etc/East_target_region_corridors.kmz", "Eastern");
mkLink($r, $prefix . "/Shore/Charts_etc/target_region_corridors.kmz", "Central");
mkLink($r, $prefix . "/Shore/Charts_etc/west_corridor_regions.kmz", "Western");
$r->endElement(); // Folder

mkLink($r, $prefix . "/Shore/Charts_etc/NOAA_chart_11340_1.kmz", "NOAA Chart");
mkLink($r, $prefix . "/Shore/Charts_etc/Ship heatmap.kmz", "Ship Heatmap");

$r->endElement(); // Document
$r->endElement(); // kml
$r->endDocument(); // XML
echo $r->outputMemory(true); // Clean up and generate a string
?>
