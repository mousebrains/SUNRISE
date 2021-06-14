<!DOCTYPE html>
<html>
<head>
<title>
SUNRISE 2021
</title>
</head>
<body>
<h1>SUNRISE 2021</h1>
<ul>
<?php
$toSkip = array(".", "..", ".dropbox", ".dropbox.cache", "Pat Welch", "js", "css", "png", "maps");
foreach (scandir(".") as $key => $val) {
	if (!in_array($val, $toSkip) and is_dir($val)) {
		echo "<li><a href='$val'>$val</a></li>\n";
	}
}
?>
</ul>
</body>
</html>
