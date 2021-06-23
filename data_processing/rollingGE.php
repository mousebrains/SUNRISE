<?php
// Pat's base Google Earth items

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


mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican 1200kHz_vector.kmz", "Pelican 1200kHz vector");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican 600kHz_vector.kmz", "Pelican 600kHz vector");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican_Density.kmz", "Pelican Density");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican_PMV.kmz", "Pelican PMV");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican_Salinity.kmz", "Pelican Salinity");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican_Salinity_Gradient.kmz", "Pelican Salinity Gradient");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Pelican_Temperature.kmz", "Pelican Temperature");

mkLink($r, $prefix . "/Processed/Rolling-2Days/WS 1200kHz_vector.kmz", "Walton Smith 1200kHz vector");
mkLink($r, $prefix . "/Processed/Rolling-2Days/WS 600kHz_vector.kmz", "Walton Smith 600kHz vector");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Walton_Smith_Density.kmz", "Walton Smith Density");
mkLink($r, $prefix . "/Processed/Rolling-2Days/WS_PMV.kmz", "Walton Smith PMV");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Walton_Smith_Salinity.kmz", "Walton Smith Salinity");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Walton_Smith_Salinity_Gradient.kmz", "Walton Smith Salinity Gradient");
mkLink($r, $prefix . "/Processed/Rolling-2Days/Walton_Smith_Temperature.kmz", "Walton Smith Temperature");




$r->endElement(); // Document
$r->endElement(); // kml
$r->endDocument(); // XML
echo $r->outputMemory(true); // Clean up and generate a string
?>
