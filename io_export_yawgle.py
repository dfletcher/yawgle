#
# Y.A.W.G.L.E.
# Yet Another WebGL Exporter
# (c) 2010 Dave Fletcher
# All Rights Reserved
#

from bpy.props import *
from mathutils import *
from functools import reduce
import os, os.path, errno, bpy, math

bl_addon_info = {
  'name': 'Y.A.W.G.L.E. Export (.html)',
  'author': 'Dave Fletcher',
  'version': '0.1',
  'blender': (2, 53, 0),
  'location': 'File > Export',
  'description': 'Y.A.W.G.L.E. Export (.html)',
  'url': 'http://anticitizenone.net/jsoe',
  'category': 'Import/Export'
}

def _formatnum(n):
  if abs(round(n) - n) < 0.0001: return str(int(round(n)))
  s = '%.4f' % n
  while s[-1] == '0': s = s[:-1]
  if s[-1] == '.': s = s[:-1]
  return s

def _rshash(key):
  a = 378551
  b = 63689
  hash = 0
  for i in range(len(key)):
    hash = hash * a + int(key[i]*1000)
    a = a * b
  return hash & 0xFFFFFFFF

def _vertex_index(vertexdata, data, datamap):
  key = _rshash(vertexdata)
  index = -1
  try:
    for i,datum in datamap[key]:
      if datum == vertexdata:
        index = i
        break
  except KeyError: datamap[key] = []
  if index == -1:
    index = len(data)
    data.append(vertexdata)
    datamap[key].append((index, vertexdata))
  return index

def _json_MESH(mesh):

  data = []
  indices = []
  datamap = {}
  for face in mesh.faces:
    swizzle = [2, 1, 0] if len(face.vertices) == 3 else [ 2, 1, 0, 3, 2, 0 ]
    for s in swizzle:
      datum = []
      if len(mesh.uv_textures):
        for t in mesh.uv_textures:
          if t.data[face.index]:
            datum += t.data[face.index].uv[s][0:2]
            break
      else: datum += [0,0]
      datum += mesh.vertices[face.vertices[s]].co[0:3]
      datum += mesh.vertices[face.vertices[s]].normal[0:3]
      indices.append(_vertex_index(datum, data, datamap))

  s = ''

  # Vertices, normals, texcoords.
  for name, positions in [
    ('texcoords', [0, 1]), ('vertices', [2, 3, 4]), ('normals', [5, 6, 7])
  ]:
    first = True
    s += ',"%s":[' % (name)
    for d in data:
      for i in positions:
        if first: first = False
        else: s += ','
        s += _formatnum(d[i])
    s += ']'

  # Indices.
  first = True
  s += ',"indices":['
  for index in indices:
    if first: first = False
    else: s += ','
    s += str(index)
  s += ']'

  return s

def _clean_name(name):
  name = name.replace('.', '_')
  name = name.replace('-', '_')
  name = name.replace('.html', '')
  name = name.replace('"', '')
  return name

class JSExporter(bpy.types.Operator):

  """Y.A.W.G.L.E. Export (.html)"""

  bl_idname = 'export.jso'
  bl_label = 'Export HTML'

  filepath = StringProperty()
  filename = StringProperty()
  directory = StringProperty()

  def execute(self, context):

    print('output: ' + self.filename)
    basename = os.path.splitext(self.filename)[0]
    classname = basename.title() + 'Class'
    jsdir = os.path.join(self.directory, "js") # TODO: make configurable
    try: os.makedirs(jsdir)
    except OSError as exc:
      if exc.errno == errno.EEXIST: pass
      else: raise
    jsfilename = '%s.js' % (basename)
    jsfile = os.path.join(jsdir, jsfilename)
    jspath = 'js/%s' % (jsfilename)

    jscode  = '// TODO: file header\n\n'
    jscode += 'function Mesh(params) {\n'
    jscode += '  this.translate = params["translate"];\n'
    jscode += '  this.rotate = params["rotate"];\n'
    jscode += '  this.scale = params["scale"];\n'
    jscode += '  this.textureID = params["texture image"];\n'
    jscode += '}\n\n'
    jscode += 'function %s(params) {\n' % (classname)
    jscode += '  this.meshes = [];\n'
    jscode += '  this.textures = [];\n'
    jscode += '  this.textureCallback = params["texture callback"];\n'
    jscode += '  this.textureArgs = params["texture arguments"];\n'
    jscode += '  this.vboCallback = params["vbo callback"];\n'
    jscode += '  this.vboArgs = params["vbo arguments"];\n'
    jscode += '}\n\n'
    jscode += '%s.prototype.load = function(loader) {\n\n' % (classname)
    jscode += '  var parent = this;\n'

    unique = []
    for img in bpy.data.images:
      if not img.filepath: continue
      file = os.path.basename(img.filepath)
      if file in unique: continue
      if not os.path.exists(os.path.join(self.directory, file)):
        # TODO: make image path configurable
        continue
      unique.append(file)
      imgid = _clean_name(file)
      imgargs = (imgid, file, img.size[0], img.size[1])
      jscode += '\n  // %s %dx%d\n' % (file, img.size[0], img.size[1])
      jscode += '  loader.loadTexture("%s", "%s", %d, %d, function(image) {\n' % imgargs
      jscode += '    parent.textures["%s"] = parent.textureCallback(image, parent.textureArgs);\n' % (imgid)
      jscode += '  });\n'

    jscode += '\n  // Javascript objects\n'
    for obj in bpy.data.objects:
      if obj.type != 'MESH': continue
      if len(obj.data.faces) == 0: continue
      objname = _clean_name(obj.name)
      mesh = obj.data
      image = 'null';
      for t in mesh.uv_textures:
        for d in t.data:
          image = _clean_name(os.path.basename(
            mesh.uv_textures[0].data[0].image.filepath
          ))
          break
      jscode += '  parent.meshes["%s"] = new Mesh({\n' % (objname)
      jscode += '    "translate": [%f, %f, %f],\n' % (
        obj.location[0],
        obj.location[1],
        obj.location[2]
      )
      jscode += '    "rotate": [%f, %f, %f],\n' % (
        math.degrees(obj.rotation_euler[0]),
        math.degrees(obj.rotation_euler[1]),
        math.degrees(obj.rotation_euler[2])
      )
      jscode += '    "scale": [%f, %f, %f],\n' % (obj.scale[0], obj.scale[1], obj.scale[2])
      jscode += '    "texture image": "%s"\n' % image
      jscode += '  });\n'

    loaded = []
    jscode += '\n  // JSON\n'
    for obj in bpy.data.objects:
      if obj.type != 'MESH': continue
      if len(obj.data.faces) == 0: continue
      mesh = obj.create_mesh(bpy.context.scene, True, 'PREVIEW')
      dataname = _clean_name(obj.data.name)
      jsonfile = os.path.join(jsdir, "%s.json" % (dataname))
      jsonpath = "js/%s.json" % (dataname)
      if not jsonpath in loaded:
        print("output mesh: %s " % (dataname))
        loaded.append(jsonpath)
        json = '{'
        json += '"name": "%s"' % (dataname)
        json += _json_MESH(mesh)
        json += '}\n'
        jscode += '  loader.loadJSONData("%s", function(data) {\n' % (jsonpath)
        jscode += '    var vbo = parent.vboCallback(data, parent.vboArgs);\n'
        for obj2 in bpy.data.objects:
          if obj2.type != 'MESH': continue
          if obj2.data and obj2.data.name == obj.data.name:
            data2name = _clean_name(obj2.name)
            jscode += '    parent.meshes["%s"].vbo = vbo;\n' % data2name
        jscode += '  });\n'

        f = open(os.path.join(self.directory, jsonfile), 'w')
        if not f: raise ('Could not open file for writing.')
        f.write(json)
        f.close()

    jscode += '}\n'

    f = open(jsfile, 'w')
    if not f: raise ('Could not open file for writing.')
    f.write(jscode)
    f.close()

    mathlib = os.path.join(jsdir, 'glMatrix.js')
    if not os.path.isfile(mathlib):
      f = open(mathlib, 'w')
      f.write(MATHLIB)
      f.close()

    loader = os.path.join(jsdir, 'webgl-jso-jqueryloader.js')
    if not os.path.isfile(loader):
      f = open(loader, 'w')
      f.write(LOADER)
      f.close()

    renderer = os.path.join(jsdir, 'webgl-jso-basicrenderer.js')
    if not os.path.isfile(renderer):
      f = open(renderer, 'w')
      f.write(RENDERER)
      f.close()

    if not os.path.isfile(self.filepath):
      f = open(self.filepath, 'w')
      f.write(
        HTML.replace(
          '${{SCENECLASSNAME}}', classname
        ).replace(
          "${{SCENEFILE}}", jspath
        )
      )
      f.close()

    return {'FINISHED'}

  def invoke(self, context, event):
    context.window_manager.add_fileselect(self)
    return {'RUNNING_MODAL'}


def menu_func(self, context):
  self.layout.operator(
    JSExporter.bl_idname,
    text='Y.A.W.G.L.E. Export (.html)'
  ).filepath = os.path.splitext(bpy.data.filepath)[0] + '.html'

def register():
  bpy.types.INFO_MT_file_export.append(menu_func)


def unregister():
  bpy.types.INFO_MT_file_export.remove(menu_func)

if __name__ == '__main__':
  register()


# -----------------------------------------------------------------------------
#   Templates
# -----------------------------------------------------------------------------

MATHLIB = """/* 
 * glMatrix.js - High performance matrix and vector operations for WebGL
 * version 0.9.5
 */
 
/*
 * Copyright (c) 2010 Brandon Jones
 *
 * This software is provided 'as-is', without any express or implied
 * warranty. In no event will the authors be held liable for any damages
 * arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 *
 *    1. The origin of this software must not be misrepresented; you must not
 *    claim that you wrote the original software. If you use this software
 *    in a product, an acknowledgment in the product documentation would be
 *    appreciated but is not required.
 *
 *    2. Altered source versions must be plainly marked as such, and must not
 *    be misrepresented as being the original software.
 *
 *    3. This notice may not be removed or altered from any source
 *    distribution.
 */

// Fallback for systems that don't support WebGL
if(typeof Float32Array != 'undefined') {
	glMatrixArrayType = Float32Array;
} else if(typeof WebGLFloatArray != 'undefined') {
	glMatrixArrayType = WebGLFloatArray; // This is officially deprecated and should dissapear in future revisions.
} else {
	glMatrixArrayType = Array;
}

/*
 * vec3 - 3 Dimensional Vector
 */
var vec3 = {};

/*
 * vec3.create
 * Creates a new instance of a vec3 using the default array type
 * Any javascript array containing at least 3 numeric elements can serve as a vec3
 *
 * Params:
 * vec - Optional, vec3 containing values to initialize with
 *
 * Returns:
 * New vec3
 */
vec3.create = function(vec) {
	var dest = new glMatrixArrayType(3);
	
	if(vec) {
		dest[0] = vec[0];
		dest[1] = vec[1];
		dest[2] = vec[2];
	}
	
	return dest;
};

/*
 * vec3.set
 * Copies the values of one vec3 to another
 *
 * Params:
 * vec - vec3 containing values to copy
 * dest - vec3 receiving copied values
 *
 * Returns:
 * dest
 */
vec3.set = function(vec, dest) {
	dest[0] = vec[0];
	dest[1] = vec[1];
	dest[2] = vec[2];
	
	return dest;
};

/*
 * vec3.add
 * Performs a vector addition
 *
 * Params:
 * vec - vec3, first operand
 * vec2 - vec3, second operand
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.add = function(vec, vec2, dest) {
	if(!dest || vec == dest) {
		vec[0] += vec2[0];
		vec[1] += vec2[1];
		vec[2] += vec2[2];
		return vec;
	}
	
	dest[0] = vec[0] + vec2[0];
	dest[1] = vec[1] + vec2[1];
	dest[2] = vec[2] + vec2[2];
	return dest;
};

/*
 * vec3.subtract
 * Performs a vector subtraction
 *
 * Params:
 * vec - vec3, first operand
 * vec2 - vec3, second operand
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.subtract = function(vec, vec2, dest) {
	if(!dest || vec == dest) {
		vec[0] -= vec2[0];
		vec[1] -= vec2[1];
		vec[2] -= vec2[2];
		return vec;
	}
	
	dest[0] = vec[0] - vec2[0];
	dest[1] = vec[1] - vec2[1];
	dest[2] = vec[2] - vec2[2];
	return dest;
};

/*
 * vec3.negate
 * Negates the components of a vec3
 *
 * Params:
 * vec - vec3 to negate
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.negate = function(vec, dest) {
	if(!dest) { dest = vec; }
	
	dest[0] = -vec[0];
	dest[1] = -vec[1];
	dest[2] = -vec[2];
	return dest;
};

/*
 * vec3.scale
 * Multiplies the components of a vec3 by a scalar value
 *
 * Params:
 * vec - vec3 to scale
 * val - Numeric value to scale by
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.scale = function(vec, val, dest) {
	if(!dest || vec == dest) {
		vec[0] *= val;
		vec[1] *= val;
		vec[2] *= val;
		return vec;
	}
	
	dest[0] = vec[0]*val;
	dest[1] = vec[1]*val;
	dest[2] = vec[2]*val;
	return dest;
};

/*
 * vec3.normalize
 * Generates a unit vector of the same direction as the provided vec3
 * If vector length is 0, returns [0, 0, 0]
 *
 * Params:
 * vec - vec3 to normalize
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.normalize = function(vec, dest) {
	if(!dest) { dest = vec; }
	
	var x = vec[0], y = vec[1], z = vec[2];
	var len = Math.sqrt(x*x + y*y + z*z);
	
	if (!len) {
		dest[0] = 0;
		dest[1] = 0;
		dest[2] = 0;
		return dest;
	} else if (len == 1) {
		dest[0] = x;
		dest[1] = y;
		dest[2] = z;
		return dest;
	}
	
	len = 1 / len;
	dest[0] = x*len;
	dest[1] = y*len;
	dest[2] = z*len;
	return dest;
};

/*
 * vec3.cross
 * Generates the cross product of two vec3s
 *
 * Params:
 * vec - vec3, first operand
 * vec2 - vec3, second operand
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.cross = function(vec, vec2, dest){
	if(!dest) { dest = vec; }
	
	var x = vec[0], y = vec[1], z = vec[2];
	var x2 = vec2[0], y2 = vec2[1], z2 = vec2[2];
	
	dest[0] = y*z2 - z*y2;
	dest[1] = z*x2 - x*z2;
	dest[2] = x*y2 - y*x2;
	return dest;
};

/*
 * vec3.length
 * Caclulates the length of a vec3
 *
 * Params:
 * vec - vec3 to calculate length of
 *
 * Returns:
 * Length of vec
 */
vec3.length = function(vec){
	var x = vec[0], y = vec[1], z = vec[2];
	return Math.sqrt(x*x + y*y + z*z);
};

/*
 * vec3.dot
 * Caclulates the dot product of two vec3s
 *
 * Params:
 * vec - vec3, first operand
 * vec2 - vec3, second operand
 *
 * Returns:
 * Dot product of vec and vec2
 */
vec3.dot = function(vec, vec2){
	return vec[0]*vec2[0] + vec[1]*vec2[1] + vec[2]*vec2[2];
};

/*
 * vec3.direction
 * Generates a unit vector pointing from one vector to another
 *
 * Params:
 * vec - origin vec3
 * vec2 - vec3 to point to
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
vec3.direction = function(vec, vec2, dest) {
	if(!dest) { dest = vec; }
	
	var x = vec[0] - vec2[0];
	var y = vec[1] - vec2[1];
	var z = vec[2] - vec2[2];
	
	var len = Math.sqrt(x*x + y*y + z*z);
	if (!len) { 
		dest[0] = 0; 
		dest[1] = 0; 
		dest[2] = 0;
		return dest; 
	}
	
	len = 1 / len;
	dest[0] = x * len; 
	dest[1] = y * len; 
	dest[2] = z * len;
	return dest; 
};

/*
 * vec3.str
 * Returns a string representation of a vector
 *
 * Params:
 * vec - vec3 to represent as a string
 *
 * Returns:
 * string representation of vec
 */
vec3.str = function(vec) {
	return '[' + vec[0] + ', ' + vec[1] + ', ' + vec[2] + ']'; 
};

/*
 * mat3 - 3x3 Matrix
 */
var mat3 = {};

/*
 * mat3.create
 * Creates a new instance of a mat3 using the default array type
 * Any javascript array containing at least 9 numeric elements can serve as a mat3
 *
 * Params:
 * mat - Optional, mat3 containing values to initialize with
 *
 * Returns:
 * New mat3
 */
mat3.create = function(mat) {
	var dest = new glMatrixArrayType(9);
	
	if(mat) {
		dest[0] = mat[0];
		dest[1] = mat[1];
		dest[2] = mat[2];
		dest[3] = mat[3];
		dest[4] = mat[4];
		dest[5] = mat[5];
		dest[6] = mat[6];
		dest[7] = mat[7];
		dest[8] = mat[8];
		dest[9] = mat[9];
	}
	
	return dest;
};

/*
 * mat3.set
 * Copies the values of one mat3 to another
 *
 * Params:
 * mat - mat3 containing values to copy
 * dest - mat3 receiving copied values
 *
 * Returns:
 * dest
 */
mat3.set = function(mat, dest) {
	dest[0] = mat[0];
	dest[1] = mat[1];
	dest[2] = mat[2];
	dest[3] = mat[3];
	dest[4] = mat[4];
	dest[5] = mat[5];
	dest[6] = mat[6];
	dest[7] = mat[7];
	dest[8] = mat[8];
	return dest;
};

/*
 * mat3.identity
 * Sets a mat3 to an identity matrix
 *
 * Params:
 * dest - mat3 to set
 *
 * Returns:
 * dest
 */
mat3.identity = function(dest) {
	dest[0] = 1;
	dest[1] = 0;
	dest[2] = 0;
	dest[3] = 0;
	dest[4] = 1;
	dest[5] = 0;
	dest[6] = 0;
	dest[7] = 0;
	dest[8] = 1;
	return dest;
};

/*
 * mat3.toMat4
 * Copies the elements of a mat3 into the upper 3x3 elements of a mat4
 *
 * Params:
 * mat - mat3 containing values to copy
 * dest - Optional, mat4 receiving copied values
 *
 * Returns:
 * dest if specified, a new mat4 otherwise
 */
mat3.toMat4 = function(mat, dest) {
	if(!dest) { dest = mat4.create(); }
	
	dest[0] = mat[0];
	dest[1] = mat[1];
	dest[2] = mat[2];
	dest[3] = 0;

	dest[4] = mat[3];
	dest[5] = mat[4];
	dest[6] = mat[5];
	dest[7] = 0;

	dest[8] = mat[6];
	dest[9] = mat[7];
	dest[10] = mat[8];
	dest[11] = 0;

	dest[12] = 0;
	dest[13] = 0;
	dest[14] = 0;
	dest[15] = 1;
	
	return dest;
}

/*
 * mat3.str
 * Returns a string representation of a mat3
 *
 * Params:
 * mat - mat3 to represent as a string
 *
 * Returns:
 * string representation of mat
 */
mat3.str = function(mat) {
	return '[' + mat[0] + ', ' + mat[1] + ', ' + mat[2] + 
		', ' + mat[3] + ', '+ mat[4] + ', ' + mat[5] + 
		', ' + mat[6] + ', ' + mat[7] + ', '+ mat[8] + ']';
};

/*
 * mat4 - 4x4 Matrix
 */
var mat4 = {};

/*
 * mat4.create
 * Creates a new instance of a mat4 using the default array type
 * Any javascript array containing at least 16 numeric elements can serve as a mat4
 *
 * Params:
 * mat - Optional, mat4 containing values to initialize with
 *
 * Returns:
 * New mat4
 */
mat4.create = function(mat) {
	var dest = new glMatrixArrayType(16);
	
	if(mat) {
		dest[0] = mat[0];
		dest[1] = mat[1];
		dest[2] = mat[2];
		dest[3] = mat[3];
		dest[4] = mat[4];
		dest[5] = mat[5];
		dest[6] = mat[6];
		dest[7] = mat[7];
		dest[8] = mat[8];
		dest[9] = mat[9];
		dest[10] = mat[10];
		dest[11] = mat[11];
		dest[12] = mat[12];
		dest[13] = mat[13];
		dest[14] = mat[14];
		dest[15] = mat[15];
	}
	
	return dest;
};

/*
 * mat4.set
 * Copies the values of one mat4 to another
 *
 * Params:
 * mat - mat4 containing values to copy
 * dest - mat4 receiving copied values
 *
 * Returns:
 * dest
 */
mat4.set = function(mat, dest) {
	dest[0] = mat[0];
	dest[1] = mat[1];
	dest[2] = mat[2];
	dest[3] = mat[3];
	dest[4] = mat[4];
	dest[5] = mat[5];
	dest[6] = mat[6];
	dest[7] = mat[7];
	dest[8] = mat[8];
	dest[9] = mat[9];
	dest[10] = mat[10];
	dest[11] = mat[11];
	dest[12] = mat[12];
	dest[13] = mat[13];
	dest[14] = mat[14];
	dest[15] = mat[15];
	return dest;
};

/*
 * mat4.identity
 * Sets a mat4 to an identity matrix
 *
 * Params:
 * dest - mat4 to set
 *
 * Returns:
 * dest
 */
mat4.identity = function(dest) {
	dest[0] = 1;
	dest[1] = 0;
	dest[2] = 0;
	dest[3] = 0;
	dest[4] = 0;
	dest[5] = 1;
	dest[6] = 0;
	dest[7] = 0;
	dest[8] = 0;
	dest[9] = 0;
	dest[10] = 1;
	dest[11] = 0;
	dest[12] = 0;
	dest[13] = 0;
	dest[14] = 0;
	dest[15] = 1;
	return dest;
};

/*
 * mat4.transpose
 * Transposes a mat4 (flips the values over the diagonal)
 *
 * Params:
 * mat - mat4 to transpose
 * dest - Optional, mat4 receiving transposed values. If not specified result is written to mat
 *
 * Returns:
 * dest is specified, mat otherwise
 */
mat4.transpose = function(mat, dest) {
	// If we are transposing ourselves we can skip a few steps but have to cache some values
	if(!dest || mat == dest) { 
		var a01 = mat[1], a02 = mat[2], a03 = mat[3];
		var a12 = mat[6], a13 = mat[7];
		var a23 = mat[11];
		
		mat[1] = mat[4];
		mat[2] = mat[8];
		mat[3] = mat[12];
		mat[4] = a01;
		mat[6] = mat[9];
		mat[7] = mat[13];
		mat[8] = a02;
		mat[9] = a12;
		mat[11] = mat[14];
		mat[12] = a03;
		mat[13] = a13;
		mat[14] = a23;
		return mat;
	}
	
	dest[0] = mat[0];
	dest[1] = mat[4];
	dest[2] = mat[8];
	dest[3] = mat[12];
	dest[4] = mat[1];
	dest[5] = mat[5];
	dest[6] = mat[9];
	dest[7] = mat[13];
	dest[8] = mat[2];
	dest[9] = mat[6];
	dest[10] = mat[10];
	dest[11] = mat[14];
	dest[12] = mat[3];
	dest[13] = mat[7];
	dest[14] = mat[11];
	dest[15] = mat[15];
	return dest;
};

/*
 * mat4.determinant
 * Calculates the determinant of a mat4
 *
 * Params:
 * mat - mat4 to calculate determinant of
 *
 * Returns:
 * determinant of mat
 */
mat4.determinant = function(mat) {
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];
	var a30 = mat[12], a31 = mat[13], a32 = mat[14], a33 = mat[15];

	return	a30*a21*a12*a03 - a20*a31*a12*a03 - a30*a11*a22*a03 + a10*a31*a22*a03 +
			a20*a11*a32*a03 - a10*a21*a32*a03 - a30*a21*a02*a13 + a20*a31*a02*a13 +
			a30*a01*a22*a13 - a00*a31*a22*a13 - a20*a01*a32*a13 + a00*a21*a32*a13 +
			a30*a11*a02*a23 - a10*a31*a02*a23 - a30*a01*a12*a23 + a00*a31*a12*a23 +
			a10*a01*a32*a23 - a00*a11*a32*a23 - a20*a11*a02*a33 + a10*a21*a02*a33 +
			a20*a01*a12*a33 - a00*a21*a12*a33 - a10*a01*a22*a33 + a00*a11*a22*a33;
};

/*
 * mat4.inverse
 * Calculates the inverse matrix of a mat4
 *
 * Params:
 * mat - mat4 to calculate inverse of
 * dest - Optional, mat4 receiving inverse matrix. If not specified result is written to mat
 *
 * Returns:
 * dest is specified, mat otherwise
 */
mat4.inverse = function(mat, dest) {
	if(!dest) { dest = mat; }
	
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];
	var a30 = mat[12], a31 = mat[13], a32 = mat[14], a33 = mat[15];
	
	var b00 = a00*a11 - a01*a10;
	var b01 = a00*a12 - a02*a10;
	var b02 = a00*a13 - a03*a10;
	var b03 = a01*a12 - a02*a11;
	var b04 = a01*a13 - a03*a11;
	var b05 = a02*a13 - a03*a12;
	var b06 = a20*a31 - a21*a30;
	var b07 = a20*a32 - a22*a30;
	var b08 = a20*a33 - a23*a30;
	var b09 = a21*a32 - a22*a31;
	var b10 = a21*a33 - a23*a31;
	var b11 = a22*a33 - a23*a32;
	
	// Calculate the determinant (inlined to avoid double-caching)
	var invDet = 1/(b00*b11 - b01*b10 + b02*b09 + b03*b08 - b04*b07 + b05*b06);
	
	dest[0] = (a11*b11 - a12*b10 + a13*b09)*invDet;
	dest[1] = (-a01*b11 + a02*b10 - a03*b09)*invDet;
	dest[2] = (a31*b05 - a32*b04 + a33*b03)*invDet;
	dest[3] = (-a21*b05 + a22*b04 - a23*b03)*invDet;
	dest[4] = (-a10*b11 + a12*b08 - a13*b07)*invDet;
	dest[5] = (a00*b11 - a02*b08 + a03*b07)*invDet;
	dest[6] = (-a30*b05 + a32*b02 - a33*b01)*invDet;
	dest[7] = (a20*b05 - a22*b02 + a23*b01)*invDet;
	dest[8] = (a10*b10 - a11*b08 + a13*b06)*invDet;
	dest[9] = (-a00*b10 + a01*b08 - a03*b06)*invDet;
	dest[10] = (a30*b04 - a31*b02 + a33*b00)*invDet;
	dest[11] = (-a20*b04 + a21*b02 - a23*b00)*invDet;
	dest[12] = (-a10*b09 + a11*b07 - a12*b06)*invDet;
	dest[13] = (a00*b09 - a01*b07 + a02*b06)*invDet;
	dest[14] = (-a30*b03 + a31*b01 - a32*b00)*invDet;
	dest[15] = (a20*b03 - a21*b01 + a22*b00)*invDet;
	
	return dest;
};

/*
 * mat4.toRotationMat
 * Copies the upper 3x3 elements of a mat4 into another mat4
 *
 * Params:
 * mat - mat4 containing values to copy
 * dest - Optional, mat4 receiving copied values
 *
 * Returns:
 * dest is specified, a new mat4 otherwise
 */
mat4.toRotationMat = function(mat, dest) {
	if(!dest) { dest = mat4.create(); }
	
	dest[0] = mat[0];
	dest[1] = mat[1];
	dest[2] = mat[2];
	dest[3] = mat[3];
	dest[4] = mat[4];
	dest[5] = mat[5];
	dest[6] = mat[6];
	dest[7] = mat[7];
	dest[8] = mat[8];
	dest[9] = mat[9];
	dest[10] = mat[10];
	dest[11] = mat[11];
	dest[12] = 0;
	dest[13] = 0;
	dest[14] = 0;
	dest[15] = 1;
	
	return dest;
};

/*
 * mat4.toMat3
 * Copies the upper 3x3 elements of a mat4 into a mat3
 *
 * Params:
 * mat - mat4 containing values to copy
 * dest - Optional, mat3 receiving copied values
 *
 * Returns:
 * dest is specified, a new mat3 otherwise
 */
mat4.toMat3 = function(mat, dest) {
	if(!dest) { dest = mat3.create(); }
	
	dest[0] = mat[0];
	dest[1] = mat[1];
	dest[2] = mat[2];
	dest[3] = mat[4];
	dest[4] = mat[5];
	dest[5] = mat[6];
	dest[6] = mat[8];
	dest[7] = mat[9];
	dest[8] = mat[10];
	
	return dest;
};

/*
 * mat4.toInverseMat3
 * Calculates the inverse of the upper 3x3 elements of a mat4 and copies the result into a mat3
 * The resulting matrix is useful for calculating transformed normals
 *
 * Params:
 * mat - mat4 containing values to invert and copy
 * dest - Optional, mat3 receiving values
 *
 * Returns:
 * dest is specified, a new mat3 otherwise
 */
mat4.toInverseMat3 = function(mat, dest) {
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10];
	
	var b01 = a22*a11-a12*a21;
	var b11 = -a22*a10+a12*a20;
	var b21 = a21*a10-a11*a20;
		
	var d = a00*b01 + a01*b11 + a02*b21;
	if (!d) { return null; }
	var id = 1/d;
	
	if(!dest) { dest = mat3.create(); }
	
	dest[0] = b01*id;
	dest[1] = (-a22*a01 + a02*a21)*id;
	dest[2] = (a12*a01 - a02*a11)*id;
	dest[3] = b11*id;
	dest[4] = (a22*a00 - a02*a20)*id;
	dest[5] = (-a12*a00 + a02*a10)*id;
	dest[6] = b21*id;
	dest[7] = (-a21*a00 + a01*a20)*id;
	dest[8] = (a11*a00 - a01*a10)*id;
	
	return dest;
};

/*
 * mat4.multiply
 * Performs a matrix multiplication
 *
 * Params:
 * mat - mat4, first operand
 * mat2 - mat4, second operand
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.multiply = function(mat, mat2, dest) {
	if(!dest) { dest = mat }
	
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];
	var a30 = mat[12], a31 = mat[13], a32 = mat[14], a33 = mat[15];
	
	var b00 = mat2[0], b01 = mat2[1], b02 = mat2[2], b03 = mat2[3];
	var b10 = mat2[4], b11 = mat2[5], b12 = mat2[6], b13 = mat2[7];
	var b20 = mat2[8], b21 = mat2[9], b22 = mat2[10], b23 = mat2[11];
	var b30 = mat2[12], b31 = mat2[13], b32 = mat2[14], b33 = mat2[15];
	
	dest[0] = b00*a00 + b01*a10 + b02*a20 + b03*a30;
	dest[1] = b00*a01 + b01*a11 + b02*a21 + b03*a31;
	dest[2] = b00*a02 + b01*a12 + b02*a22 + b03*a32;
	dest[3] = b00*a03 + b01*a13 + b02*a23 + b03*a33;
	dest[4] = b10*a00 + b11*a10 + b12*a20 + b13*a30;
	dest[5] = b10*a01 + b11*a11 + b12*a21 + b13*a31;
	dest[6] = b10*a02 + b11*a12 + b12*a22 + b13*a32;
	dest[7] = b10*a03 + b11*a13 + b12*a23 + b13*a33;
	dest[8] = b20*a00 + b21*a10 + b22*a20 + b23*a30;
	dest[9] = b20*a01 + b21*a11 + b22*a21 + b23*a31;
	dest[10] = b20*a02 + b21*a12 + b22*a22 + b23*a32;
	dest[11] = b20*a03 + b21*a13 + b22*a23 + b23*a33;
	dest[12] = b30*a00 + b31*a10 + b32*a20 + b33*a30;
	dest[13] = b30*a01 + b31*a11 + b32*a21 + b33*a31;
	dest[14] = b30*a02 + b31*a12 + b32*a22 + b33*a32;
	dest[15] = b30*a03 + b31*a13 + b32*a23 + b33*a33;
	
	return dest;
};

/*
 * mat4.multiplyVec3
 * Transforms a vec3 with the given matrix
 * 4th vector component is implicitly '1'
 *
 * Params:
 * mat - mat4 to transform the vector with
 * vec - vec3 to transform
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
mat4.multiplyVec3 = function(mat, vec, dest) {
	if(!dest) { dest = vec }
	
	var x = vec[0], y = vec[1], z = vec[2];
	
	dest[0] = mat[0]*x + mat[4]*y + mat[8]*z + mat[12];
	dest[1] = mat[1]*x + mat[5]*y + mat[9]*z + mat[13];
	dest[2] = mat[2]*x + mat[6]*y + mat[10]*z + mat[14];
	
	return dest;
};

/*
 * mat4.multiplyVec4
 * Transforms a vec4 with the given matrix
 *
 * Params:
 * mat - mat4 to transform the vector with
 * vec - vec4 to transform
 * dest - Optional, vec4 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
mat4.multiplyVec4 = function(mat, vec, dest) {
	if(!dest) { dest = vec }
	
	var x = vec[0], y = vec[1], z = vec[2], w = vec[3];
	
	dest[0] = mat[0]*x + mat[4]*y + mat[8]*z + mat[12]*w;
	dest[1] = mat[1]*x + mat[5]*y + mat[9]*z + mat[13]*w;
	dest[2] = mat[2]*x + mat[6]*y + mat[10]*z + mat[14]*w;
	dest[4] = mat[4]*x + mat[7]*y + mat[11]*z + mat[15]*w;
	
	return dest;
};

/*
 * mat4.translate
 * Translates a matrix by the given vector
 *
 * Params:
 * mat - mat4 to translate
 * vec - vec3 specifying the translation
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.translate = function(mat, vec, dest) {
	var x = vec[0], y = vec[1], z = vec[2];
	
	if(!dest || mat == dest) {
		mat[12] = mat[0]*x + mat[4]*y + mat[8]*z + mat[12];
		mat[13] = mat[1]*x + mat[5]*y + mat[9]*z + mat[13];
		mat[14] = mat[2]*x + mat[6]*y + mat[10]*z + mat[14];
		mat[15] = mat[3]*x + mat[7]*y + mat[11]*z + mat[15];
		return mat;
	}
	
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];
	
	dest[0] = a00;
	dest[1] = a01;
	dest[2] = a02;
	dest[3] = a03;
	dest[4] = a10;
	dest[5] = a11;
	dest[6] = a12;
	dest[7] = a13;
	dest[8] = a20;
	dest[9] = a21;
	dest[10] = a22;
	dest[11] = a23;
	
	dest[12] = a00*x + a10*y + a20*z + mat[12];
	dest[13] = a01*x + a11*y + a21*z + mat[13];
	dest[14] = a02*x + a12*y + a22*z + mat[14];
	dest[15] = a03*x + a13*y + a23*z + mat[15];
	return dest;
};

/*
 * mat4.scale
 * Scales a matrix by the given vector
 *
 * Params:
 * mat - mat4 to scale
 * vec - vec3 specifying the scale for each axis
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.scale = function(mat, vec, dest) {
	var x = vec[0], y = vec[1], z = vec[2];
	
	if(!dest || mat == dest) {
		mat[0] *= x;
		mat[1] *= x;
		mat[2] *= x;
		mat[3] *= x;
		mat[4] *= y;
		mat[5] *= y;
		mat[6] *= y;
		mat[7] *= y;
		mat[8] *= z;
		mat[9] *= z;
		mat[10] *= z;
		mat[11] *= z;
		return mat;
	}
	
	dest[0] = mat[0]*x;
	dest[1] = mat[1]*x;
	dest[2] = mat[2]*x;
	dest[3] = mat[3]*x;
	dest[4] = mat[4]*y;
	dest[5] = mat[5]*y;
	dest[6] = mat[6]*y;
	dest[7] = mat[7]*y;
	dest[8] = mat[8]*z;
	dest[9] = mat[9]*z;
	dest[10] = mat[10]*z;
	dest[11] = mat[11]*z;
	dest[12] = mat[12];
	dest[13] = mat[13];
	dest[14] = mat[14];
	dest[15] = mat[15];
	return dest;
};

/*
 * mat4.rotate
 * Rotates a matrix by the given angle around the specified axis
 * If rotating around a primary axis (X,Y,Z) one of the specialized rotation functions should be used instead for performance
 *
 * Params:
 * mat - mat4 to rotate
 * angle - angle (in radians) to rotate
 * axis - vec3 representing the axis to rotate around 
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.rotate = function(mat, angle, axis, dest) {
	var x = axis[0], y = axis[1], z = axis[2];
	var len = Math.sqrt(x*x + y*y + z*z);
	if (!len) { return null; }
	if (len != 1) {
		len = 1 / len;
		x *= len; 
		y *= len; 
		z *= len;
	}
	
	var s = Math.sin(angle);
	var c = Math.cos(angle);
	var t = 1-c;
	
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];
	
	// Construct the elements of the rotation matrix
	var b00 = x*x*t + c, b01 = y*x*t + z*s, b02 = z*x*t - y*s;
	var b10 = x*y*t - z*s, b11 = y*y*t + c, b12 = z*y*t + x*s;
	var b20 = x*z*t + y*s, b21 = y*z*t - x*s, b22 = z*z*t + c;
	
	if(!dest) { 
		dest = mat 
	} else if(mat != dest) { // If the source and destination differ, copy the unchanged last row
		dest[12] = mat[12];
		dest[13] = mat[13];
		dest[14] = mat[14];
		dest[15] = mat[15];
	}
	
	// Perform rotation-specific matrix multiplication
	dest[0] = a00*b00 + a10*b01 + a20*b02;
	dest[1] = a01*b00 + a11*b01 + a21*b02;
	dest[2] = a02*b00 + a12*b01 + a22*b02;
	dest[3] = a03*b00 + a13*b01 + a23*b02;
	
	dest[4] = a00*b10 + a10*b11 + a20*b12;
	dest[5] = a01*b10 + a11*b11 + a21*b12;
	dest[6] = a02*b10 + a12*b11 + a22*b12;
	dest[7] = a03*b10 + a13*b11 + a23*b12;
	
	dest[8] = a00*b20 + a10*b21 + a20*b22;
	dest[9] = a01*b20 + a11*b21 + a21*b22;
	dest[10] = a02*b20 + a12*b21 + a22*b22;
	dest[11] = a03*b20 + a13*b21 + a23*b22;
	return dest;
};

/*
 * mat4.rotateX
 * Rotates a matrix by the given angle around the X axis
 *
 * Params:
 * mat - mat4 to rotate
 * angle - angle (in radians) to rotate
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.rotateX = function(mat, angle, dest) {
	var s = Math.sin(angle);
	var c = Math.cos(angle);
	
	// Cache the matrix values (makes for huge speed increases!)
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];

	if(!dest) { 
		dest = mat 
	} else if(mat != dest) { // If the source and destination differ, copy the unchanged rows
		dest[0] = mat[0];
		dest[1] = mat[1];
		dest[2] = mat[2];
		dest[3] = mat[3];
		
		dest[12] = mat[12];
		dest[13] = mat[13];
		dest[14] = mat[14];
		dest[15] = mat[15];
	}
	
	// Perform axis-specific matrix multiplication
	dest[4] = a10*c + a20*s;
	dest[5] = a11*c + a21*s;
	dest[6] = a12*c + a22*s;
	dest[7] = a13*c + a23*s;
	
	dest[8] = a10*-s + a20*c;
	dest[9] = a11*-s + a21*c;
	dest[10] = a12*-s + a22*c;
	dest[11] = a13*-s + a23*c;
	return dest;
};

/*
 * mat4.rotateY
 * Rotates a matrix by the given angle around the Y axis
 *
 * Params:
 * mat - mat4 to rotate
 * angle - angle (in radians) to rotate
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.rotateY = function(mat, angle, dest) {
	var s = Math.sin(angle);
	var c = Math.cos(angle);
	
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a20 = mat[8], a21 = mat[9], a22 = mat[10], a23 = mat[11];
	
	if(!dest) { 
		dest = mat 
	} else if(mat != dest) { // If the source and destination differ, copy the unchanged rows
		dest[4] = mat[4];
		dest[5] = mat[5];
		dest[6] = mat[6];
		dest[7] = mat[7];
		
		dest[12] = mat[12];
		dest[13] = mat[13];
		dest[14] = mat[14];
		dest[15] = mat[15];
	}
	
	// Perform axis-specific matrix multiplication
	dest[0] = a00*c + a20*-s;
	dest[1] = a01*c + a21*-s;
	dest[2] = a02*c + a22*-s;
	dest[3] = a03*c + a23*-s;
	
	dest[8] = a00*s + a20*c;
	dest[9] = a01*s + a21*c;
	dest[10] = a02*s + a22*c;
	dest[11] = a03*s + a23*c;
	return dest;
};

/*
 * mat4.rotateZ
 * Rotates a matrix by the given angle around the Z axis
 *
 * Params:
 * mat - mat4 to rotate
 * angle - angle (in radians) to rotate
 * dest - Optional, mat4 receiving operation result. If not specified result is written to mat
 *
 * Returns:
 * dest if specified, mat otherwise
 */
mat4.rotateZ = function(mat, angle, dest) {
	var s = Math.sin(angle);
	var c = Math.cos(angle);
	
	// Cache the matrix values (makes for huge speed increases!)
	var a00 = mat[0], a01 = mat[1], a02 = mat[2], a03 = mat[3];
	var a10 = mat[4], a11 = mat[5], a12 = mat[6], a13 = mat[7];
	
	if(!dest) { 
		dest = mat 
	} else if(mat != dest) { // If the source and destination differ, copy the unchanged last row
		dest[8] = mat[8];
		dest[9] = mat[9];
		dest[10] = mat[10];
		dest[11] = mat[11];
		
		dest[12] = mat[12];
		dest[13] = mat[13];
		dest[14] = mat[14];
		dest[15] = mat[15];
	}
	
	// Perform axis-specific matrix multiplication
	dest[0] = a00*c + a10*s;
	dest[1] = a01*c + a11*s;
	dest[2] = a02*c + a12*s;
	dest[3] = a03*c + a13*s;
	
	dest[4] = a00*-s + a10*c;
	dest[5] = a01*-s + a11*c;
	dest[6] = a02*-s + a12*c;
	dest[7] = a03*-s + a13*c;
	
	return dest;
};

/*
 * mat4.frustum
 * Generates a frustum matrix with the given bounds
 *
 * Params:
 * left, right - scalar, left and right bounds of the frustum
 * bottom, top - scalar, bottom and top bounds of the frustum
 * near, far - scalar, near and far bounds of the frustum
 * dest - Optional, mat4 frustum matrix will be written into
 *
 * Returns:
 * dest if specified, a new mat4 otherwise
 */
mat4.frustum = function(left, right, bottom, top, near, far, dest) {
	if(!dest) { dest = mat4.create(); }
	var rl = (right - left);
	var tb = (top - bottom);
	var fn = (far - near);
	dest[0] = (near*2) / rl;
	dest[1] = 0;
	dest[2] = 0;
	dest[3] = 0;
	dest[4] = 0;
	dest[5] = (near*2) / tb;
	dest[6] = 0;
	dest[7] = 0;
	dest[8] = (right + left) / rl;
	dest[9] = (top + bottom) / tb;
	dest[10] = -(far + near) / fn;
	dest[11] = -1;
	dest[12] = 0;
	dest[13] = 0;
	dest[14] = -(far*near*2) / fn;
	dest[15] = 0;
	return dest;
};

/*
 * mat4.perspective
 * Generates a perspective projection matrix with the given bounds
 *
 * Params:
 * fovy - scalar, vertical field of view
 * aspect - scalar, aspect ratio. typically viewport width/height
 * near, far - scalar, near and far bounds of the frustum
 * dest - Optional, mat4 frustum matrix will be written into
 *
 * Returns:
 * dest if specified, a new mat4 otherwise
 */
mat4.perspective = function(fovy, aspect, near, far, dest) {
	var top = near*Math.tan(fovy*Math.PI / 360.0);
	var right = top*aspect;
	return mat4.frustum(-right, right, -top, top, near, far, dest);
};

/*
 * mat4.ortho
 * Generates a orthogonal projection matrix with the given bounds
 *
 * Params:
 * left, right - scalar, left and right bounds of the frustum
 * bottom, top - scalar, bottom and top bounds of the frustum
 * near, far - scalar, near and far bounds of the frustum
 * dest - Optional, mat4 frustum matrix will be written into
 *
 * Returns:
 * dest if specified, a new mat4 otherwise
 */
mat4.ortho = function(left, right, bottom, top, near, far, dest) {
	if(!dest) { dest = mat4.create(); }
	var rl = (right - left);
	var tb = (top - bottom);
	var fn = (far - near);
	dest[0] = 2 / rl;
	dest[1] = 0;
	dest[2] = 0;
	dest[3] = 0;
	dest[4] = 0;
	dest[5] = 2 / tb;
	dest[6] = 0;
	dest[7] = 0;
	dest[8] = 0;
	dest[9] = 0;
	dest[10] = -2 / fn;
	dest[11] = 0;
	dest[12] = -(left + right) / rl;
	dest[13] = -(top + bottom) / tb;
	dest[14] = -(far + near) / fn;
	dest[15] = 1;
	return dest;
};

/*
 * mat4.ortho
 * Generates a look-at matrix with the given eye position, focal point, and up axis
 *
 * Params:
 * eye - vec3, position of the viewer
 * center - vec3, point the viewer is looking at
 * up - vec3 pointing "up"
 * dest - Optional, mat4 frustum matrix will be written into
 *
 * Returns:
 * dest if specified, a new mat4 otherwise
 */
mat4.lookAt = function(eye, center, up, dest) {
	if(!dest) { dest = mat4.create(); }
	
	var eyex = eye[0],
		eyey = eye[1],
		eyez = eye[2],
		upx = up[0],
		upy = up[1],
		upz = up[2],
		centerx = center[0],
		centery = center[1],
		centerz = center[2];

	if (eyex == centerx && eyey == centery && eyez == centerz) {
		return mat4.identity(dest);
	}
	
	var z0,z1,z2,x0,x1,x2,y0,y1,y2,len;
	
	//vec3.direction(eye, center, z);
	z0 = eyex - center[0];
	z1 = eyey - center[1];
	z2 = eyez - center[2];
	
	// normalize (no check needed for 0 because of early return)
	len = 1/Math.sqrt(z0*z0 + z1*z1 + z2*z2);
	z0 *= len;
	z1 *= len;
	z2 *= len;
	
	//vec3.normalize(vec3.cross(up, z, x));
	x0 = upy*z2 - upz*z1;
	x1 = upz*z0 - upx*z2;
	x2 = upx*z1 - upy*z0;
	len = Math.sqrt(x0*x0 + x1*x1 + x2*x2);
	if (!len) {
		x0 = 0;
		x1 = 0;
		x2 = 0;
	} else {
		len = 1/len;
		x0 *= len;
		x1 *= len;
		x2 *= len;
	};
	
	//vec3.normalize(vec3.cross(z, x, y));
	y0 = z1*x2 - z2*x1;
	y1 = z2*x0 - z0*x2;
	y2 = z0*x1 - z1*x0;
	
	len = Math.sqrt(y0*y0 + y1*y1 + y2*y2);
	if (!len) {
		y0 = 0;
		y1 = 0;
		y2 = 0;
	} else {
		len = 1/len;
		y0 *= len;
		y1 *= len;
		y2 *= len;
	}
	
	dest[0] = x0;
	dest[1] = y0;
	dest[2] = z0;
	dest[3] = 0;
	dest[4] = x1;
	dest[5] = y1;
	dest[6] = z1;
	dest[7] = 0;
	dest[8] = x2;
	dest[9] = y2;
	dest[10] = z2;
	dest[11] = 0;
	dest[12] = -(x0*eyex + x1*eyey + x2*eyez);
	dest[13] = -(y0*eyex + y1*eyey + y2*eyez);
	dest[14] = -(z0*eyex + z1*eyey + z2*eyez);
	dest[15] = 1;
	
	return dest;
};

/*
 * mat4.str
 * Returns a string representation of a mat4
 *
 * Params:
 * mat - mat4 to represent as a string
 *
 * Returns:
 * string representation of mat
 */
mat4.str = function(mat) {
	return '[' + mat[0] + ', ' + mat[1] + ', ' + mat[2] + ', ' + mat[3] + 
		', '+ mat[4] + ', ' + mat[5] + ', ' + mat[6] + ', ' + mat[7] + 
		', '+ mat[8] + ', ' + mat[9] + ', ' + mat[10] + ', ' + mat[11] + 
		', '+ mat[12] + ', ' + mat[13] + ', ' + mat[14] + ', ' + mat[15] + ']';
};

/*
 * quat4 - Quaternions 
 */
quat4 = {};

/*
 * quat4.create
 * Creates a new instance of a quat4 using the default array type
 * Any javascript array containing at least 4 numeric elements can serve as a quat4
 *
 * Params:
 * quat - Optional, quat4 containing values to initialize with
 *
 * Returns:
 * New quat4
 */
quat4.create = function(quat) {
	var dest = new glMatrixArrayType(4);
	
	if(quat) {
		dest[0] = quat[0];
		dest[1] = quat[1];
		dest[2] = quat[2];
		dest[3] = quat[3];
	}
	
	return dest;
};

/*
 * quat4.set
 * Copies the values of one quat4 to another
 *
 * Params:
 * quat - quat4 containing values to copy
 * dest - quat4 receiving copied values
 *
 * Returns:
 * dest
 */
quat4.set = function(quat, dest) {
	dest[0] = quat[0];
	dest[1] = quat[1];
	dest[2] = quat[2];
	dest[3] = quat[3];
	
	return dest;
};

/*
 * quat4.calculateW
 * Calculates the W component of a quat4 from the X, Y, and Z components.
 * Assumes that quaternion is 1 unit in length. 
 * Any existing W component will be ignored. 
 *
 * Params:
 * quat - quat4 to calculate W component of
 * dest - Optional, quat4 receiving calculated values. If not specified result is written to quat
 *
 * Returns:
 * dest if specified, quat otherwise
 */
quat4.calculateW = function(quat, dest) {
	var x = quat[0], y = quat[1], z = quat[2];

	if(!dest || quat == dest) {
		quat[3] = -Math.sqrt(Math.abs(1.0 - x*x - y*y - z*z));
		return quat;
	}
	dest[0] = x;
	dest[1] = y;
	dest[2] = z;
	dest[3] = -Math.sqrt(Math.abs(1.0 - x*x - y*y - z*z));
	return dest;
}

/*
 * quat4.inverse
 * Calculates the inverse of a quat4
 *
 * Params:
 * quat - quat4 to calculate inverse of
 * dest - Optional, quat4 receiving inverse values. If not specified result is written to quat
 *
 * Returns:
 * dest if specified, quat otherwise
 */
quat4.inverse = function(quat, dest) {
	if(!dest || quat == dest) {
		quat[0] *= 1;
		quat[1] *= 1;
		quat[2] *= 1;
		return quat;
	}
	dest[0] = -quat[0];
	dest[1] = -quat[1];
	dest[2] = -quat[2];
	dest[3] = quat[3];
	return dest;
}

/*
 * quat4.length
 * Calculates the length of a quat4
 *
 * Params:
 * quat - quat4 to calculate length of
 *
 * Returns:
 * Length of quat
 */
quat4.length = function(quat) {
	var x = quat[0], y = quat[1], z = quat[2], w = quat[3];
	return Math.sqrt(x*x + y*y + z*z + w*w);
}

/*
 * quat4.normalize
 * Generates a unit quaternion of the same direction as the provided quat4
 * If quaternion length is 0, returns [0, 0, 0, 0]
 *
 * Params:
 * quat - quat4 to normalize
 * dest - Optional, quat4 receiving operation result. If not specified result is written to quat
 *
 * Returns:
 * dest if specified, quat otherwise
 */
quat4.normalize = function(quat, dest) {
	if(!dest) { dest = quat; }
	
	var x = quat[0], y = quat[1], z = quat[2], w = quat[3];
	var len = Math.sqrt(x*x + y*y + z*z + w*w);
	if(len == 0) {
		dest[0] = 0;
		dest[1] = 0;
		dest[2] = 0;
		dest[3] = 0;
		return dest;
	}
	len = 1/len;
	dest[0] = x * len;
	dest[1] = y * len;
	dest[2] = z * len;
	dest[3] = w * len;
	
	return dest;
}

/*
 * quat4.multiply
 * Performs a quaternion multiplication
 *
 * Params:
 * quat - quat4, first operand
 * quat2 - quat4, second operand
 * dest - Optional, quat4 receiving operation result. If not specified result is written to quat
 *
 * Returns:
 * dest if specified, quat otherwise
 */
quat4.multiply = function(quat, quat2, dest) {
	if(!dest) { dest = quat; }
	
	var qax = quat[0], qay = quat[1], qaz = quat[2], qaw = quat[3];
	var qbx = quat2[0], qby = quat2[1], qbz = quat2[2], qbw = quat2[3];
	
	dest[0] = qax*qbw + qaw*qbx + qay*qbz - qaz*qby;
	dest[1] = qay*qbw + qaw*qby + qaz*qbx - qax*qbz;
	dest[2] = qaz*qbw + qaw*qbz + qax*qby - qay*qbx;
	dest[3] = qaw*qbw - qax*qbx - qay*qby - qaz*qbz;
	
	return dest;
}

/*
 * quat4.multiplyVec3
 * Transforms a vec3 with the given quaternion
 *
 * Params:
 * quat - quat4 to transform the vector with
 * vec - vec3 to transform
 * dest - Optional, vec3 receiving operation result. If not specified result is written to vec
 *
 * Returns:
 * dest if specified, vec otherwise
 */
quat4.multiplyVec3 = function(quat, vec, dest) {
	if(!dest) { dest = vec; }
	
	var x = vec[0], y = vec[1], z = vec[2];
	var qx = quat[0], qy = quat[1], qz = quat[2], qw = quat[3];

	// calculate quat * vec
	var ix = qw*x + qy*z - qz*y;
	var iy = qw*y + qz*x - qx*z;
	var iz = qw*z + qx*y - qy*x;
	var iw = -qx*x - qy*y - qz*z;
	
	// calculate result * inverse quat
	dest[0] = ix*qw + iw*-qx + iy*-qz - iz*-qy;
	dest[1] = iy*qw + iw*-qy + iz*-qx - ix*-qz;
	dest[2] = iz*qw + iw*-qz + ix*-qy - iy*-qx;
	
	return dest;
}

/*
 * quat4.toMat3
 * Calculates a 3x3 matrix from the given quat4
 *
 * Params:
 * quat - quat4 to create matrix from
 * dest - Optional, mat3 receiving operation result
 *
 * Returns:
 * dest if specified, a new mat3 otherwise
 */
quat4.toMat3 = function(quat, dest) {
	if(!dest) { dest = mat3.create(); }
	
	var x = quat[0], y = quat[1], z = quat[2], w = quat[3];

	var x2 = x + x;
	var y2 = y + y;
	var z2 = z + z;

	var xx = x*x2;
	var xy = x*y2;
	var xz = x*z2;

	var yy = y*y2;
	var yz = y*z2;
	var zz = z*z2;

	var wx = w*x2;
	var wy = w*y2;
	var wz = w*z2;

	dest[0] = 1 - (yy + zz);
	dest[1] = xy - wz;
	dest[2] = xz + wy;

	dest[3] = xy + wz;
	dest[4] = 1 - (xx + zz);
	dest[5] = yz - wx;

	dest[6] = xz - wy;
	dest[7] = yz + wx;
	dest[8] = 1 - (xx + yy);
	
	return dest;
}

/*
 * quat4.toMat4
 * Calculates a 4x4 matrix from the given quat4
 *
 * Params:
 * quat - quat4 to create matrix from
 * dest - Optional, mat4 receiving operation result
 *
 * Returns:
 * dest if specified, a new mat4 otherwise
 */
quat4.toMat4 = function(quat, dest) {
	if(!dest) { dest = mat4.create(); }
	
	var x = quat[0], y = quat[1], z = quat[2], w = quat[3];

	var x2 = x + x;
	var y2 = y + y;
	var z2 = z + z;

	var xx = x*x2;
	var xy = x*y2;
	var xz = x*z2;

	var yy = y*y2;
	var yz = y*z2;
	var zz = z*z2;

	var wx = w*x2;
	var wy = w*y2;
	var wz = w*z2;

	dest[0] = 1 - (yy + zz);
	dest[1] = xy - wz;
	dest[2] = xz + wy;
	dest[3] = 0;

	dest[4] = xy + wz;
	dest[5] = 1 - (xx + zz);
	dest[6] = yz - wx;
	dest[7] = 0;

	dest[8] = xz - wy;
	dest[9] = yz + wx;
	dest[10] = 1 - (xx + yy);
	dest[11] = 0;

	dest[12] = 0;
	dest[13] = 0;
	dest[14] = 0;
	dest[15] = 1;
	
	return dest;
}

/*
 * quat4.str
 * Returns a string representation of a quaternion
 *
 * Params:
 * quat - quat4 to represent as a string
 *
 * Returns:
 * string representation of quat
 */
quat4.str = function(quat) {
	return '[' + quat[0] + ', ' + quat[1] + ', ' + quat[2] + ', ' + quat[3] + ']'; 
};
"""

LOADER = """// TODO: header

// ----------------------------
// JQueryLoader
// ----------------------------

function JQueryLoader(params) {
  this.requestsout = 0;
  this.requestsin = 0;
  this.expander = params['expander'];
  this.label = params['label'];
  this.complete_callback = params['complete callback'];
  this.complete_callback_args = params['complete callback arguments'];
  this.percent_display = params['percent label'];
  this.itemcount_display = params['itemcount label'];
  this.resources = [];
  this.update();
}

JQueryLoader.prototype.update = function() {
  var percent = Math.floor(this.percent());
  $(this.expander).css('width', percent + '%');
  $(this.percent_display).text(percent + '%');
  $(this.itemcount_display).text(this.requestsin + '/' + this.requestsout);
  if (percent == 100) {
    this.complete_callback(this.complete_callback_args);
  }
}

JQueryLoader.prototype.request = function() {
  this.requestsout++;
  this.update();
}

JQueryLoader.prototype.response = function() {
  this.requestsin++;
  this.update();
}

JQueryLoader.prototype.percent = function() {
  if (this.requestsout == 0) return 0;
  return (this.requestsin / this.requestsout) * 100.0;
}

JQueryLoader.prototype.loadJSONData = function(src, callback) {
  var loader = this;
  if (loader.resources[src]) {
    // Don't load JSON more than once.
    return;
  }
  loader.resources[src] = true;
  loader.request();
  $.getJSON(src, function(data) {
    callback(data);
    loader.response();
  });
}

JQueryLoader.prototype.loadTexture = function(
  id, src, width, height, callback
) {
  var loader = this;
  if (loader.resources[src]) {
    // Don't load images more than once.
    return;
  }
  loader.resources[src] = true;
  loader.request();
  var img = $("<img/>")
    .attr("src", src)
    .attr("id", id)
    .attr("width", width + "px")
    .attr("height", height + "px")
    .css("display", "none")
    .appendTo("BODY")
    .load(function() {
      callback(this);
      loader.response();
    });
}
"""

RENDERER = """// TODO: header

var lastboundtexture = -1;
var lastboundvbo = -1;
var lastboundprogram = -1;
var last_program_id = 0;
var last_vbo_id = 0;
var WebGLDebugUtils;

function log(msg) {
  if (window.console && window.console.log) {
    window.console.log(msg);
  }
}

function hashcounter(hash) {
  var size = 0, key;
  for (key in hash) {
    if (hash.hasOwnProperty(key)) {
      size++;
    }
  }
  return size;
};

function BasicRenderer(params) {

  this.programs = [];
  this.params = params;
  this.canvas = document.getElementById(params['canvas id']);

  // Init OpenGL.
  this.gl = null;
  try { this.gl = this.canvas.getContext("webgl"); }
  catch (e) { }
  try { if (!this.gl) this.gl = this.canvas.getContext("moz-webgl"); }
  catch (e) { }
  try { if (!this.gl) this.gl = this.canvas.getContext("webkit-3d"); }
  catch (e) { }
  try { if (!this.gl) this.gl = this.canvas.getContext("experimental-webgl"); }
  catch (e) { }
  if (!this.gl) {
    return;
  }

  // Debug context
  if (WebGLDebugUtils) {
    this.gl = WebGLDebugUtils.makeDebugContext(this.gl);
  }

  // GL init.
  this.gl.clearColor(
    params['clear color'][0], params['clear color'][1],
    params['clear color'][2], params['clear color'][3]
  );
  this.gl.clearDepth(params['clear depth']);
  this.gl.enable(this.gl.DEPTH_TEST);
  this.gl.enable(this.gl.BLEND);
  this.gl.blendFunc(this.gl.SRC_ALPHA, this.gl.ONE_MINUS_SRC_ALPHA);
  this.gl.enableVertexAttribArray(0); // Normals.
  this.gl.enableVertexAttribArray(1); // Texture coordinates.
  this.gl.enableVertexAttribArray(2); // Vertices.

  // Init camera.
  this.camerastack = [];
  this.camerastacklen = 0;
  var camera = mat4.create();
  mat4.identity(camera);
  mat4.lookAt([0, -5, 4], [0, 1, 0], [0, 1, 0], camera);
  log('camera: ' + mat4.str(camera));
  this.pushCamera(camera);

  // Init shaders.
  this.gl.program = this.newProgram(
    params['vertex program id'], params['fragment program id']
  );
}

BasicRenderer.prototype.reshape = function() {
  this.width = this.canvas.clientWidth;
  this.height = this.canvas.clientHeight;
  this.gl.viewport(0, 0, this.width, this.height);
  this.projectionstack = [];
  this.projectionstacklen = 0;
  var projection = mat4.create();
  mat4.identity(projection);
  mat4.perspective(35, this.width/this.height, 1, 10000, projection);
  //mat4.lookAt([0, 0, 7], [0, 0, 0], [0, 1, 0], projection);
  log('projection1: ' + mat4.str(projection));
  this.pushProjection(projection);
  log('projection2: ' + mat4.str(this.projection()));
}

BasicRenderer.prototype.newProgram = function(vprogid, fprogid) {
  var program = new Object;
  program.id = ++last_program_id;
  program.shader = this.gl.createProgram();
  var vprog = this.getShader(vprogid);
  var fprog = this.getShader(fprogid);
  this.gl.attachShader(program.shader, vprog);
  this.gl.attachShader(program.shader, fprog);
  var attributes = this.params['vertex attribute names'];
  for (var i in attributes) {
    this.gl.bindAttribLocation (program.shader, parseInt(i), attributes[i]);
  }
  this.gl.linkProgram(program.shader);
  var linked = this.gl.getProgramParameter(program.shader, this.gl.LINK_STATUS);
  if (!linked) {
    var error = this.gl.getProgramInfoLog (program.shader);
    alert("Error linking program: " + error);
    this.gl.deleteProgram(program.shader);
    this.gl.deleteProgram(fprog);
    this.gl.deleteProgram(vprog);
    return null;
  }
  this.gl.useProgram(program.shader);
  this.gl.uniform1i(this.gl.getUniformLocation(
    program.shader, this.params['sampler2d variable']
  ), 0);
  this.gl.uniform1i(this.gl.getUniformLocation(
    program.shader, this.params['samplercube variable']
  ), 0);
  this.gl.uniform3f(this.gl.getUniformLocation(
    program.shader, this.params['light variable']
  ), 0, 7, 4);
  program.u_normalMatrixLoc = this.gl.getUniformLocation(
    program.shader, this.params['normal matrix variable']
  );
  program.u_modelViewMatrixLoc = this.gl.getUniformLocation(
    program.shader, this.params['modelview matrix variable']
  );
  program.u_projMatrixLoc = this.gl.getUniformLocation(
    program.shader, this.params['projection matrix variable']
  );
  program.u_objectMatrixLoc = this.gl.getUniformLocation(
    program.shader, this.params['object matrix variable']
  );
  program.normalMatrix = mat4.create();
  mat4.identity(program.normalMatrix);
  this.programs[this.programs.length] = program;
  return program;
}

BasicRenderer.prototype.pushCamera = function(camera) {
  this.camerastack[this.camerastacklen++] = camera;
}

BasicRenderer.prototype.camera = function() {
  return this.camerastack[this.camerastacklen-1];
}

BasicRenderer.prototype.popCamera = function() {
  var idx = --this.camerastacklen;
  var rcamera = this.camerastack[idx];
  delete this.camerastack[idx];
  return rcamera;
}

BasicRenderer.prototype.pushProjection = function(projection) {
  this.projectionstack[this.projectionstacklen++] = projection;
}

BasicRenderer.prototype.projection = function() {
  return this.projectionstack[this.projectionstacklen-1];
}

BasicRenderer.prototype.popProjection = function() {
  var idx = --this.projectionstacklen;
  var rprojection = this.projectionstack[idx];
  delete this.projectionstack[idx];
  return rprojection;
}

BasicRenderer.prototype.getShader = function(id) {
  var shaderScript = document.getElementById(id);
  if (!shaderScript) return null;
  var str = "";
  var k = shaderScript.firstChild;
  while (k) {
    if (k.nodeType == 3) str += k.textContent;
    k = k.nextSibling;
  }
  var shader;
  if (shaderScript.type == "x-shader/x-fragment") {
    shader = this.gl.createShader(this.gl.FRAGMENT_SHADER);
  }
  else if (shaderScript.type == "x-shader/x-vertex") {
    shader = this.gl.createShader(this.gl.VERTEX_SHADER);
  }
  else {
    return null;
  }
  this.gl.shaderSource(shader, str);
  this.gl.compileShader(shader);

  if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
    alert(this.gl.getShaderInfoLog(shader));
    return null;
  }
  return shader;
}

BasicRenderer.prototype.standardTexture = function(image, args) {
  var gl = args[0];
  var texture = gl.createTexture();
  texture.image = image;
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, texture.image);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  //gl.generateMipmap(gl.TEXTURE_2D);
  gl.bindTexture(gl.TEXTURE_2D, null);
  return texture;
}

BasicRenderer.prototype.standardVBO = function(data, args) {

  var renderer = args[0];
  var gl = renderer.gl;
  var vbo = new StandardVBO();

  // Vertex buffer.
  vbo.vertexData = data["vertices"];
  vbo.vertexObject = gl.createBuffer();

  // Normals buffer.
  vbo.normalsData = data["normals"];
  vbo.normalsObject = gl.createBuffer();

  // Texcoords buffer.
  vbo.texcoordsData = data["texcoords"];
  if (vbo.texcoordsData) {
    vbo.texcoordsObject = gl.createBuffer();
  }
  else {
    vbo.texcoordsObject = null;
  }

  // Index buffer.
  vbo.indicesData = data["indices"];
  vbo.indicesObject = gl.createBuffer();

  renderer.updateVBO(vbo);
  
  return vbo;
}

BasicRenderer.prototype.updateVBO = function(vbo) {
  var gl = this.gl;
  vbo.vertices = new Float32Array(vbo.vertexData);
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo.vertexObject);
  gl.bufferData(gl.ARRAY_BUFFER, vbo.vertices, gl.STATIC_DRAW);
  vbo.normals = new Float32Array(vbo.normalsData);
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo.normalsObject);
  gl.bufferData(gl.ARRAY_BUFFER, vbo.normals, gl.STATIC_DRAW);
  if (vbo.texcoordsData) {
    vbo.texcoords = new Float32Array(vbo.texcoordsData);
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo.texcoordsObject);
    gl.bufferData(gl.ARRAY_BUFFER, vbo.texcoords, gl.STATIC_DRAW);
  }
  gl.bindBuffer(gl.ARRAY_BUFFER, null);
  vbo.indices = new Uint16Array(vbo.indicesData);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, vbo.indicesObject);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, vbo.indices, gl.STATIC_DRAW);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, null);
  vbo.vertexCount = vbo.indicesData.length;
}

BasicRenderer.prototype.renderMesh = function(mesh) {
  if (mesh.program) {
    var program = mesh.program;
    var changed = (lastboundprogram != mesh.program.id);
  }
  else {
    var program = this.gl.program;
    var changed = (lastboundprogram != this.gl.program.id);
  }
  if (changed) {
    this.gl.useProgram(program.shader);
    lastboundprogram = program.id;
  }
  if (mesh.vbo.id != lastboundvbo) {
    if (!mesh.vbo.bind(this.gl)) return;
    lastboundvbo = mesh.vbo.id;
  }
  if (mesh.texture != lastboundtexture) {
    this.gl.bindTexture(this.gl.TEXTURE_2D, mesh.texture);
    lastboundtexture = mesh.texture;
  }
  //log('camera: ' + mat4.str(this.camera()));
  //log('projection: ' + mat4.str(this.projection()));
  this.gl.uniformMatrix4fv(program.u_projMatrixLoc, false, this.projection());
  this.gl.uniformMatrix4fv(program.u_modelViewMatrixLoc, false, this.camera());
  this.gl.uniformMatrix4fv(program.u_objectMatrixLoc, false, mesh.objectMatrix);
  this.gl.uniformMatrix4fv(program.u_normalMatrixLoc, false, program.normalMatrix);
  this.gl.drawElements(this.gl.TRIANGLES, mesh.vbo.vertexCount, this.gl.UNSIGNED_SHORT, 0);
}

BasicRenderer.prototype.setObjectMatrix = function(mesh) {
  if (!mesh.objectMatrix) {
    mesh.objectMatrix = mat4.create();
  }
  mat4.identity(mesh.objectMatrix);
  mat4.translate(mesh.objectMatrix, [mesh.translate[0], mesh.translate[1], mesh.translate[2]]);
  mat4.rotate(mesh.objectMatrix, mesh.rotate[2] * Math.PI / 180.0, [0.0, 0.0, 1.0]);
  mat4.rotate(mesh.objectMatrix, mesh.rotate[1] * Math.PI / 180.0, [0.0, 1.0, 0.0]);
  mat4.rotate(mesh.objectMatrix, mesh.rotate[0] * Math.PI / 180.0, [1.0, 0.0, 0.0]);
  mat4.scale(mesh.objectMatrix, [mesh.scale[0], mesh.scale[1], mesh.scale[2]]);
}

BasicRenderer.prototype.prepareMeshes = function(scene) {
  for (i in scene.meshes) {
    var mesh = scene.meshes[i];
    this.setObjectMatrix(mesh);
    log(i + ': ' + mat4.str(mesh.objectMatrix));
    mesh.texture = scene.textures[mesh.textureID];
  }
}

BasicRenderer.prototype.render = function(scene) {
  var clear = true;
  if (arguments.length > 1) {
    clear = arguments[1];
  }
  if (clear) {
    this.gl.clear(this.gl.COLOR_BUFFER_BIT | this.gl.DEPTH_BUFFER_BIT);
  }
  var camera = this.camera();
  mat4.set(camera, this.gl.program.normalMatrix);
  mat4.toInverseMat3(this.gl.program.normalMatrix);
  mat4.transpose(this.gl.program.normalMatrix);
  for (i in this.programs) {
    var program = this.programs[i];
    if (program.id == this.gl.program.id) continue;
    mat4.set(this.gl.program.normalMatrix, program.normalMatrix);
  }
  for (i in scene.meshes) {
    this.renderMesh(scene.meshes[i]);
  }
}

function StandardVBO() {
  this.id = ++last_vbo_id;
}

StandardVBO.prototype.bind = function(gl) {
  gl.bindBuffer(gl.ARRAY_BUFFER, this.vertexObject);
  gl.vertexAttribPointer(2, 3, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, this.normalsObject);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, this.texcoordsObject);
  gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indicesObject);
  return true;
}

BasicRenderer.prototype._rewriteMeshData = function(data, matrix) {
  var newdata = [];
  var numvertices = data.length / 3;
  for (var i = 0; i < numvertices; i++) {
    var index = i * 3;
    var vector = vec3.create([data[index+0], data[index+1], data[index+2]]);
    mat4.multiplyVec3(matrix, vector);
    newdata[newdata.length] = vector[0];
    newdata[newdata.length] = vector[1];
    newdata[newdata.length] = vector[2];
  }
  return newdata;
}

BasicRenderer.prototype._rewriteIndices = function(data, base) {
  var newdata = [];
  for (var i in data) {
    newdata[i] = data[i] + base;
  }
  return newdata;
}

BasicRenderer.prototype.combineMeshes = function(name, meshes, meshlist) {
  var combinedmesh = new Mesh({
    "translate": [0, 0, 0],
    "rotate": [0, 0, 0],
    "scale": [1, 1, 1],
  });
  var vertexData = [];
  var texcoordsData = [];
  var normalsData = [];
  var indicesData = [];
  var indexBase = 0;
  for (i in meshlist) {
    var meshname = meshlist[i];
    if (!meshname) continue;
    var mesh = meshes[meshname];
    if (!mesh) continue;
    vertexData = vertexData.concat(this._rewriteMeshData(mesh.vbo.vertexData, mesh.objectMatrix));
    texcoordsData = texcoordsData.concat(mesh.vbo.texcoordsData);
    normalsData = normalsData.concat(mesh.vbo.normalsData);
    indicesData = indicesData.concat(this._rewriteIndices(mesh.vbo.indicesData, indexBase));
    combinedmesh.textureID = mesh.textureID;
    combinedmesh.texture = mesh.texture;
    indexBase += mesh.vbo.vertexData.length / 3;
    delete meshes[meshname];
  }
  data = {
    "vertices": vertexData,
    "texcoords": texcoordsData,
    "normals": normalsData,
    "indices": indicesData
  };
  combinedmesh.vbo = this.standardVBO(data, [this]);
  this.setObjectMatrix(combinedmesh);
  meshes[name] = combinedmesh;
  return combinedmesh;
}
"""

HTML = """<html>
  <head>
    <title>Blender -> JSO WebGL Example</title>
    <style type='text/css'>
      BODY {
        font-family: Arial,Geneva,Helvetica,sans-serif;
      }
      #loadbox {
        display: none;
        width: 400px;
        padding: 12px;
        margin: 128px auto;
        border: 1px solid #000;
      }
      #loadbox .label {
        font-weight: bold;
        padding-bottom: 12px;
      }
      #loadbox .progress {
        width: 400px;
        height: 22px;
        border: 1px solid #000;
      }
      #loadbox .progress .bar {
        height: 22px;
        width: 0px;
        background-color: #CCC;
      }
      #loadbox .progress .label {
        position: absolute;
        font-size: 12px;
        font-weight: normal;
        padding: 3px 0 0 6px;
      }
      #canvas-wrapper {
        display: none;
      width: 800px;
      height: 600px;
        border: 1px solid black;
        margin: 32px auto;
      }
      #no-canvas3d P {
        text-align: center;
        margin-top: 64px;
      }
    </style>
  </head>
  <body>
    <div id='loadbox'>
      <div class='label'>Loading...</div>
      <div class='progress'>
        <div class='label'>
          <span class='percent'></span>
          <span class='items'></span>
        </div>
        <div class='bar'></div>
      </div>
    </div>
    <div id='canvas-wrapper'>
      <canvas id='canvas3d' width='800' height='600'></canvas>
    </div>
    <div id='no-canvas3d'>
      <noscript><p>This application requires a browser with WebGL support.</p></noscript>
    </div>
    <script type='text/javascript' src='http://code.jquery.com/jquery-1.4.3.min.js'></script>
    <script type='text/javascript' src='js/glMatrix.js'></script>
    <script type='text/javascript' src='js/webgl-jso-jqueryloader.js'></script>
    <script type='text/javascript' src='js/webgl-jso-basicrenderer.js'></script>
    <script type='text/javascript' src='${{SCENEFILE}}'></script>
    <script id='vprog' type='x-shader/x-vertex'>
      uniform mat4 u_modelViewMatrix;
      uniform mat4 u_objectMatrix;
      uniform mat4 u_normalMatrix;
      uniform mat4 u_projMatrix;
      uniform vec3 lightDir;
      attribute vec3 vNormal;
      attribute vec2 vTexCoord;
      attribute vec4 vPosition;
      varying float v_Dot;
      varying vec2 v_texCoord;
      void main() {
        gl_Position = u_projMatrix * u_modelViewMatrix * u_objectMatrix * vPosition;
        v_texCoord = vTexCoord.st;
        vec4 transNormal = u_normalMatrix * vec4(vNormal, 1);
        v_Dot = max(dot(transNormal.xyz, lightDir), 0.65);
      }
    </script>
    <script id='fprog' type='x-shader/x-fragment'>
      #ifdef GL_ES
        precision mediump float;
      #endif
      uniform sampler2D sampler2d;
      varying float v_Dot;
      varying vec2 v_texCoord;
      void main() {
        vec2 texCoord = vec2(v_texCoord.s, 1.0 - v_texCoord.t);
        vec4 color = texture2D(sampler2d, texCoord);
        //gl_FragColor = vec4(color.xyz * v_Dot, 1.0);
        gl_FragColor = vec4(color.xyz, 1.0);
      }
    </script>
    <script type='text/javascript'>

      $(document).ready(function() {

        // Create a renderer.
        var renderer = new BasicRenderer({
          'canvas id': 'canvas3d',
          'clear depth': 10000,
          'clear color': [ 0.97, 0.97, 0.97, 1 ],
          'vertex program id': 'vprog',
          'fragment program id': 'fprog',
          'light variable': 'lightDir',
          'sampler2d variable': 'sampler2d',
          'normal matrix variable': 'u_normalMatrix',
          'object matrix variable': 'u_objectMatrix',
          'modelview matrix variable': 'u_modelViewMatrix',
          'projection matrix variable': 'u_projMatrix',
          'vertex attribute names': [ 'vNormal', 'vTexCoord', 'vPosition' ],
        });

        // Check if this is a WebGL capable browser.
        if (!renderer.gl) {
          $('#no-canvas3d').css('display', 'block');
          $('#no-canvas3d').html('<p>This application requires a browser with WebGL support.</p>');
          return;
        }

        // Load scene.
        var scene = new ${{SCENECLASSNAME}} ({
          'texture callback': renderer.standardTexture,
          'texture arguments': [ renderer.gl ],
          'vbo callback': renderer.standardVBO,
          'vbo arguments': [ renderer ]
        });

        // Loader object loads images, JS objects, and reports loading status.
        var loader = new JQueryLoader({
          'expander': '#loadbox .progress .bar',
          'percent label': false, //'#loadbox .progress .label .percent',
          'itemcount label': '#loadbox .progress .label .items',
          'complete callback': function() {
            $('#loadbox').css('display', 'none');
            var canvas = $('#canvas3d');
            $('#canvas-wrapper').css('display', 'block');
            canvas.css('display', 'block');
            renderer.prepareMeshes(scene);
            renderer.reshape(canvas.width(), canvas.height());
            setInterval(function() {
              // Main loop.
	      mat4.rotate(renderer.camera(), 0.5 * Math.PI / 180.0, [0,0,1]);
              renderer.render(scene);
            }, 25);
          }
        });

        // Everything's ready, display the loading box and load.
        $('#loadbox').css('display', 'block');
        scene.load(loader);

      });
    </script>
  </body>
</html>
"""
