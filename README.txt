
--------------------------
Y.A.W.G.L.E.
Yet Another WebGL Exporter
(c) 2010 Dave Fletcher
All Rights Reserved
--------------------------

INTRODUCTION
------------

Yawgle exports JSON objects from your meshes and creates example HTML,
renderer, and loader files.

It currently works with Blender 2.5x.


INSTALLATION
------------

Drop io_export_yawgle.py into your 2.x/scripts/addons directory. In
Blender,  File -> User Preferences -> Add-Ons, enable
"Y.A.W.G.L.E. Export (.html)". Close the preferences window and press
Ctrl-u to save your settings.

Note that Ctrl-u also saves whatever you have open as the default document,
so you probably want to do this immediately after launching Blender, before
opening files or making other changes.

Yawgle will appear in the File -> Export menu once enabled.


WEB SERVER CONFIGURATION
------------------------

Yawgle produces JSON files containing vertex, normal and texture coordinate
data. JSON may not work from your local desktop - the generated files will
need to be served from a web server that maps the .json file extension to
mime type: application/json.


KNOWN LIMITATIONS
-----------------

 * Currently does not use Blender camera, it's hard coded in renderer.
   Coming soon.

 * Currently does not use Blender lamps, it's hard coded in renderer.
   Coming soon.
