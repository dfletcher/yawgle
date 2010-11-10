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

def _vertex_index(vertexdata, data, datamap):
  key = reduce(lambda x,y: x*y, vertexdata)
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
      datum += mesh.vertices[face.vertices[s]].co[0:3]
      datum += mesh.vertices[face.vertices[s]].normal[0:3]
      if len(mesh.uv_textures):
        for t in mesh.uv_textures:
          if t.data[face.index]:
            datum += t.data[face.index].uv[s][0:2]
            break
      else:
        datum += [0,0]
      indices.append(_vertex_index(datum, data, datamap))

  s = ''

  # Vertices, normals, texcoords.
  for name, positions in [
    ('vertices', [0, 1, 2]), ('normals', [3, 4, 5]), ('texcoords', [6, 7])
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
            jscode += '    parent.meshes["%s"].vbo = vbo;\n' % (data2name)
        jscode += '  });\n'

        f = open(os.path.join(self.directory, jsonfile), 'w')
        if not f: raise ('Could not open file for writing.')
        f.write(json)
        f.close()

    jscode += '\n}\n'

    f = open(jsfile, 'w')
    if not f: raise ('Could not open file for writing.')
    f.write(jscode)
    f.close()

    j3dimath = os.path.join(jsdir, 'J3DIMath.js')
    if not os.path.isfile(j3dimath):
      f = open(j3dimath, 'w')
      f.write(J3DIMATH)
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
      f.write(HTML.replace('${{SCENECLASSNAME}}', classname))
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

J3DIMATH = """
/*
 * Copyright (C) 2009 Apple Inc. All Rights Reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY APPLE INC. ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL APPLE INC. OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

 // J3DI (Jedi) - A support library for WebGL.

/*
    J3DI Math Classes. Currently includes:

        J3DIMatrix4 - A 4x4 Matrix
*/

/*
    J3DIMatrix4 class

    This class implements a 4x4 matrix. It has functions which duplicate the
    functionality of the OpenGL matrix stack and glut functions. On browsers
    that support it, CSSMatrix is used to accelerate operations.

    IDL:

    [
        Constructor(in J3DIMatrix4 matrix),                 // copy passed matrix into new J3DIMatrix4
        Constructor(in sequence<float> array)               // create new J3DIMatrix4 with 16 floats (row major)
        Constructor()                                       // create new J3DIMatrix4 with identity matrix
    ]
    interface J3DIMatrix4 {
        void load(in J3DIMatrix4 matrix);                   // copy the values from the passed matrix
        void load(in sequence<float> array);                // copy 16 floats into the matrix
        sequence<float> getAsArray();                       // return the matrix as an array of 16 floats
        Float32Array getAsFloat32Array();             // return the matrix as a Float32Array with 16 values
        void setUniform(in WebGLRenderingContext ctx,       // Send the matrix to the passed uniform location in the passed context
                        in WebGLUniformLocation loc,
                        in boolean transpose);
        void makeIdentity();                                // replace the matrix with identity
        void transpose();                                   // replace the matrix with its transpose
        void invert();                                      // replace the matrix with its inverse

        void translate(in float x, in float y, in float z); // multiply the matrix by passed translation values on the right
        void translate(in J3DVector3 v);                    // multiply the matrix by passed translation values on the right
        void scale(in float x, in float y, in float z);     // multiply the matrix by passed scale values on the right
        void scale(in J3DVector3 v);                        // multiply the matrix by passed scale values on the right
        void rotate(in float angle,                         // multiply the matrix by passed rotation values on the right
                    in float x, in float y, in float z);    // (angle is in degrees)
        void rotate(in float angle, in J3DVector3 v);       // multiply the matrix by passed rotation values on the right
                                                            // (angle is in degrees)
        void multiply(in CanvasMatrix matrix);              // multiply the matrix by the passed matrix on the right
        void divide(in float divisor);                      // divide the matrix by the passed divisor
        void ortho(in float left, in float right,           // multiply the matrix by the passed ortho values on the right
                   in float bottom, in float top,
                   in float near, in float far);
        void frustum(in float left, in float right,         // multiply the matrix by the passed frustum values on the right
                     in float bottom, in float top,
                     in float near, in float far);
        void perspective(in float fovy, in float aspect,    // multiply the matrix by the passed perspective values on the right
                         in float zNear, in float zFar);
        void lookat(in J3DVector3 eye,                      // multiply the matrix by the passed lookat
                in J3DVector3 center,  in J3DVector3 up);   // values on the right
         bool decompose(in J3DVector3 translate,            // decompose the matrix into the passed vector
                        in J3DVector3 rotate,
                        in J3DVector3 scale,
                        in J3DVector3 skew,
                        in sequence<float> perspective);
    }

    [
        Constructor(in J3DVector3 vector),                  // copy passed vector into new J3DVector3
        Constructor(in sequence<float> array)               // create new J3DVector3 with 3 floats from array
        Constructor(in float x, in float y, in float z)     // create new J3DVector3 with 3 floats
        Constructor()                                       // create new J3DVector3 with (0,0,0)
    ]
    interface J3DVector3 {
        void load(in J3DVector3 vector);                    // copy the values from the passed vector
        void load(in sequence<float> array);                // copy 3 floats into the vector from array
        void load(in float x, in float y, in float z);      // copy 3 floats into the vector
        sequence<float> getAsArray();                       // return the vector as an array of 3 floats
        Float32Array getAsFloat32Array();             // return the matrix as a Float32Array with 16 values
        void multMatrix(in J3DIMatrix4 matrix);             // multiply the vector by the passed matrix (on the right)
        float vectorLength();                               // return the length of the vector
        float dot();                                        // return the dot product of the vector
        void cross(in J3DVector3 v);                        // replace the vector with vector x v
        void divide(in float divisor);                      // divide the vector by the passed divisor
    }
*/

J3DIHasCSSMatrix = false;
J3DIHasCSSMatrixCopy = false;
/*
if ("WebKitCSSMatrix" in window && ("media" in window && window.media.matchMedium("(-webkit-transform-3d)")) ||
                                   ("styleMedia" in window && window.styleMedia.matchMedium("(-webkit-transform-3d)"))) {
    J3DIHasCSSMatrix = true;
    if ("copy" in WebKitCSSMatrix.prototype)
        J3DIHasCSSMatrixCopy = true;
}
*/

//  console.log("J3DIHasCSSMatrix="+J3DIHasCSSMatrix);
//  console.log("J3DIHasCSSMatrixCopy="+J3DIHasCSSMatrixCopy);

//
// J3DIMatrix4
//
J3DIMatrix4 = function(m)
{
    if (J3DIHasCSSMatrix)
        this.$matrix = new WebKitCSSMatrix;
    else
        this.$matrix = new Object;

    if (typeof m == 'object') {
        if ("length" in m && m.length >= 16) {
            this.load(m);
            return;
        }
        else if (m instanceof J3DIMatrix4) {
            this.load(m);
            return;
        }
    }
    this.makeIdentity();
}

J3DIMatrix4.prototype.load = function()
{
    if (arguments.length == 1 && typeof arguments[0] == 'object') {
        var matrix;

        if (arguments[0] instanceof J3DIMatrix4) {
            matrix = arguments[0].$matrix;

            this.$matrix.m11 = matrix.m11;
            this.$matrix.m12 = matrix.m12;
            this.$matrix.m13 = matrix.m13;
            this.$matrix.m14 = matrix.m14;

            this.$matrix.m21 = matrix.m21;
            this.$matrix.m22 = matrix.m22;
            this.$matrix.m23 = matrix.m23;
            this.$matrix.m24 = matrix.m24;

            this.$matrix.m31 = matrix.m31;
            this.$matrix.m32 = matrix.m32;
            this.$matrix.m33 = matrix.m33;
            this.$matrix.m34 = matrix.m34;

            this.$matrix.m41 = matrix.m41;
            this.$matrix.m42 = matrix.m42;
            this.$matrix.m43 = matrix.m43;
            this.$matrix.m44 = matrix.m44;
            return;
        }
        else
            matrix = arguments[0];

        if ("length" in matrix && matrix.length >= 16) {
            this.$matrix.m11 = matrix[0];
            this.$matrix.m12 = matrix[1];
            this.$matrix.m13 = matrix[2];
            this.$matrix.m14 = matrix[3];

            this.$matrix.m21 = matrix[4];
            this.$matrix.m22 = matrix[5];
            this.$matrix.m23 = matrix[6];
            this.$matrix.m24 = matrix[7];

            this.$matrix.m31 = matrix[8];
            this.$matrix.m32 = matrix[9];
            this.$matrix.m33 = matrix[10];
            this.$matrix.m34 = matrix[11];

            this.$matrix.m41 = matrix[12];
            this.$matrix.m42 = matrix[13];
            this.$matrix.m43 = matrix[14];
            this.$matrix.m44 = matrix[15];
            return;
        }
    }

    this.makeIdentity();
}

J3DIMatrix4.prototype.getAsArray = function()
{
    return [
        this.$matrix.m11, this.$matrix.m12, this.$matrix.m13, this.$matrix.m14,
        this.$matrix.m21, this.$matrix.m22, this.$matrix.m23, this.$matrix.m24,
        this.$matrix.m31, this.$matrix.m32, this.$matrix.m33, this.$matrix.m34,
        this.$matrix.m41, this.$matrix.m42, this.$matrix.m43, this.$matrix.m44
    ];
}

J3DIMatrix4.prototype.getAsFloat32Array = function()
{
    if (J3DIHasCSSMatrixCopy) {
        var array = new Float32Array(16);
        this.$matrix.copy(array);
        return array;
    }
    return new Float32Array(this.getAsArray());
}

J3DIMatrix4.prototype.setUniform = function(ctx, loc, transpose)
{
    if (J3DIMatrix4.setUniformArray == undefined) {
        J3DIMatrix4.setUniformWebGLArray = new Float32Array(16);
        J3DIMatrix4.setUniformArray = new Array(16);
    }

    if (J3DIHasCSSMatrixCopy)
        this.$matrix.copy(J3DIMatrix4.setUniformWebGLArray);
    else {
        J3DIMatrix4.setUniformArray[0] = this.$matrix.m11;
        J3DIMatrix4.setUniformArray[1] = this.$matrix.m12;
        J3DIMatrix4.setUniformArray[2] = this.$matrix.m13;
        J3DIMatrix4.setUniformArray[3] = this.$matrix.m14;
        J3DIMatrix4.setUniformArray[4] = this.$matrix.m21;
        J3DIMatrix4.setUniformArray[5] = this.$matrix.m22;
        J3DIMatrix4.setUniformArray[6] = this.$matrix.m23;
        J3DIMatrix4.setUniformArray[7] = this.$matrix.m24;
        J3DIMatrix4.setUniformArray[8] = this.$matrix.m31;
        J3DIMatrix4.setUniformArray[9] = this.$matrix.m32;
        J3DIMatrix4.setUniformArray[10] = this.$matrix.m33;
        J3DIMatrix4.setUniformArray[11] = this.$matrix.m34;
        J3DIMatrix4.setUniformArray[12] = this.$matrix.m41;
        J3DIMatrix4.setUniformArray[13] = this.$matrix.m42;
        J3DIMatrix4.setUniformArray[14] = this.$matrix.m43;
        J3DIMatrix4.setUniformArray[15] = this.$matrix.m44;

        J3DIMatrix4.setUniformWebGLArray.set(J3DIMatrix4.setUniformArray);
    }

    ctx.uniformMatrix4fv(loc, transpose, J3DIMatrix4.setUniformWebGLArray);
}

J3DIMatrix4.prototype.makeIdentity = function()
{
    this.$matrix.m11 = 1;
    this.$matrix.m12 = 0;
    this.$matrix.m13 = 0;
    this.$matrix.m14 = 0;

    this.$matrix.m21 = 0;
    this.$matrix.m22 = 1;
    this.$matrix.m23 = 0;
    this.$matrix.m24 = 0;

    this.$matrix.m31 = 0;
    this.$matrix.m32 = 0;
    this.$matrix.m33 = 1;
    this.$matrix.m34 = 0;

    this.$matrix.m41 = 0;
    this.$matrix.m42 = 0;
    this.$matrix.m43 = 0;
    this.$matrix.m44 = 1;
}

J3DIMatrix4.prototype.transpose = function()
{
    var tmp = this.$matrix.m12;
    this.$matrix.m12 = this.$matrix.m21;
    this.$matrix.m21 = tmp;

    tmp = this.$matrix.m13;
    this.$matrix.m13 = this.$matrix.m31;
    this.$matrix.m31 = tmp;

    tmp = this.$matrix.m14;
    this.$matrix.m14 = this.$matrix.m41;
    this.$matrix.m41 = tmp;

    tmp = this.$matrix.m23;
    this.$matrix.m23 = this.$matrix.m32;
    this.$matrix.m32 = tmp;

    tmp = this.$matrix.m24;
    this.$matrix.m24 = this.$matrix.m42;
    this.$matrix.m42 = tmp;

    tmp = this.$matrix.m34;
    this.$matrix.m34 = this.$matrix.m43;
    this.$matrix.m43 = tmp;
}

J3DIMatrix4.prototype.invert = function()
{
    if (J3DIHasCSSMatrix) {
        this.$matrix = this.$matrix.inverse();
        return;
    }

    // Calculate the 4x4 determinant
    // If the determinant is zero,
    // then the inverse matrix is not unique.
    var det = this._determinant4x4();

    if (Math.abs(det) < 1e-8)
        return null;

    this._makeAdjoint();

    // Scale the adjoint matrix to get the inverse
    this.$matrix.m11 /= det;
    this.$matrix.m12 /= det;
    this.$matrix.m13 /= det;
    this.$matrix.m14 /= det;

    this.$matrix.m21 /= det;
    this.$matrix.m22 /= det;
    this.$matrix.m23 /= det;
    this.$matrix.m24 /= det;

    this.$matrix.m31 /= det;
    this.$matrix.m32 /= det;
    this.$matrix.m33 /= det;
    this.$matrix.m34 /= det;

    this.$matrix.m41 /= det;
    this.$matrix.m42 /= det;
    this.$matrix.m43 /= det;
    this.$matrix.m44 /= det;
}

J3DIMatrix4.prototype.translate = function(x,y,z)
{
    if (typeof x == 'object' && "length" in x) {
        var t = x;
        x = t[0];
        y = t[1];
        z = t[2];
    }
    else {
        if (x == undefined)
            x = 0;
        if (y == undefined)
            y = 0;
        if (z == undefined)
            z = 0;
    }

    if (J3DIHasCSSMatrix) {
        this.$matrix = this.$matrix.translate(x, y, z);
        return;
    }

    var matrix = new J3DIMatrix4();
    matrix.$matrix.m41 = x;
    matrix.$matrix.m42 = y;
    matrix.$matrix.m43 = z;

    this.multiply(matrix);
}

J3DIMatrix4.prototype.scale = function(x,y,z)
{
    if (typeof x == 'object' && "length" in x) {
        var t = x;
        x = t[0];
        y = t[1];
        z = t[2];
    }
    else {
        if (x == undefined)
            x = 1;
        if (z == undefined) {
            if (y == undefined) {
                y = x;
                z = x;
            }
            else
                z = 1;
        }
        else if (y == undefined)
            y = x;
    }

    if (J3DIHasCSSMatrix) {
        this.$matrix = this.$matrix.scale(x, y, z);
        return;
    }

    var matrix = new J3DIMatrix4();
    matrix.$matrix.m11 = x;
    matrix.$matrix.m22 = y;
    matrix.$matrix.m33 = z;

    this.multiply(matrix);
}

J3DIMatrix4.prototype.rotate = function(angle,x,y,z)
{
    // Forms are (angle, x,y,z), (angle,vector), (angleX, angleY, angleZ), (angle)
    if (typeof x == 'object' && "length" in x) {
        var t = x;
        x = t[0];
        y = t[1];
        z = t[2];
    }
    else {
        if (arguments.length == 1) {
            x = 0;
            y = 0;
            z = 1;
        }
        else if (arguments.length == 3) {
            this.rotate(angle, 1,0,0); // about X axis
            this.rotate(x, 0,1,0); // about Y axis
            this.rotate(y, 0,0,1); // about Z axis
            return;
        }
    }

    if (J3DIHasCSSMatrix) {
        this.$matrix = this.$matrix.rotateAxisAngle(x, y, z, angle);
        return;
    }

    // angles are in degrees. Switch to radians
    angle = angle / 180 * Math.PI;

    angle /= 2;
    var sinA = Math.sin(angle);
    var cosA = Math.cos(angle);
    var sinA2 = sinA * sinA;

    // normalize
    var len = Math.sqrt(x * x + y * y + z * z);
    if (len == 0) {
        // bad vector, just use something reasonable
        x = 0;
        y = 0;
        z = 1;
    } else if (len != 1) {
        x /= len;
        y /= len;
        z /= len;
    }

    var mat = new J3DIMatrix4();

    // optimize case where axis is along major axis
    if (x == 1 && y == 0 && z == 0) {
        mat.$matrix.m11 = 1;
        mat.$matrix.m12 = 0;
        mat.$matrix.m13 = 0;
        mat.$matrix.m21 = 0;
        mat.$matrix.m22 = 1 - 2 * sinA2;
        mat.$matrix.m23 = 2 * sinA * cosA;
        mat.$matrix.m31 = 0;
        mat.$matrix.m32 = -2 * sinA * cosA;
        mat.$matrix.m33 = 1 - 2 * sinA2;
        mat.$matrix.m14 = mat.$matrix.m24 = mat.$matrix.m34 = 0;
        mat.$matrix.m41 = mat.$matrix.m42 = mat.$matrix.m43 = 0;
        mat.$matrix.m44 = 1;
    } else if (x == 0 && y == 1 && z == 0) {
        mat.$matrix.m11 = 1 - 2 * sinA2;
        mat.$matrix.m12 = 0;
        mat.$matrix.m13 = -2 * sinA * cosA;
        mat.$matrix.m21 = 0;
        mat.$matrix.m22 = 1;
        mat.$matrix.m23 = 0;
        mat.$matrix.m31 = 2 * sinA * cosA;
        mat.$matrix.m32 = 0;
        mat.$matrix.m33 = 1 - 2 * sinA2;
        mat.$matrix.m14 = mat.$matrix.m24 = mat.$matrix.m34 = 0;
        mat.$matrix.m41 = mat.$matrix.m42 = mat.$matrix.m43 = 0;
        mat.$matrix.m44 = 1;
    } else if (x == 0 && y == 0 && z == 1) {
        mat.$matrix.m11 = 1 - 2 * sinA2;
        mat.$matrix.m12 = 2 * sinA * cosA;
        mat.$matrix.m13 = 0;
        mat.$matrix.m21 = -2 * sinA * cosA;
        mat.$matrix.m22 = 1 - 2 * sinA2;
        mat.$matrix.m23 = 0;
        mat.$matrix.m31 = 0;
        mat.$matrix.m32 = 0;
        mat.$matrix.m33 = 1;
        mat.$matrix.m14 = mat.$matrix.m24 = mat.$matrix.m34 = 0;
        mat.$matrix.m41 = mat.$matrix.m42 = mat.$matrix.m43 = 0;
        mat.$matrix.m44 = 1;
    } else {
        var x2 = x*x;
        var y2 = y*y;
        var z2 = z*z;

        mat.$matrix.m11 = 1 - 2 * (y2 + z2) * sinA2;
        mat.$matrix.m12 = 2 * (x * y * sinA2 + z * sinA * cosA);
        mat.$matrix.m13 = 2 * (x * z * sinA2 - y * sinA * cosA);
        mat.$matrix.m21 = 2 * (y * x * sinA2 - z * sinA * cosA);
        mat.$matrix.m22 = 1 - 2 * (z2 + x2) * sinA2;
        mat.$matrix.m23 = 2 * (y * z * sinA2 + x * sinA * cosA);
        mat.$matrix.m31 = 2 * (z * x * sinA2 + y * sinA * cosA);
        mat.$matrix.m32 = 2 * (z * y * sinA2 - x * sinA * cosA);
        mat.$matrix.m33 = 1 - 2 * (x2 + y2) * sinA2;
        mat.$matrix.m14 = mat.$matrix.m24 = mat.$matrix.m34 = 0;
        mat.$matrix.m41 = mat.$matrix.m42 = mat.$matrix.m43 = 0;
        mat.$matrix.m44 = 1;
    }
    this.multiply(mat);
}

J3DIMatrix4.prototype.multiply = function(mat)
{
    if (J3DIHasCSSMatrix) {
        this.$matrix = this.$matrix.multiply(mat.$matrix);
        return;
    }

    var m11 = (mat.$matrix.m11 * this.$matrix.m11 + mat.$matrix.m12 * this.$matrix.m21
               + mat.$matrix.m13 * this.$matrix.m31 + mat.$matrix.m14 * this.$matrix.m41);
    var m12 = (mat.$matrix.m11 * this.$matrix.m12 + mat.$matrix.m12 * this.$matrix.m22
               + mat.$matrix.m13 * this.$matrix.m32 + mat.$matrix.m14 * this.$matrix.m42);
    var m13 = (mat.$matrix.m11 * this.$matrix.m13 + mat.$matrix.m12 * this.$matrix.m23
               + mat.$matrix.m13 * this.$matrix.m33 + mat.$matrix.m14 * this.$matrix.m43);
    var m14 = (mat.$matrix.m11 * this.$matrix.m14 + mat.$matrix.m12 * this.$matrix.m24
               + mat.$matrix.m13 * this.$matrix.m34 + mat.$matrix.m14 * this.$matrix.m44);

    var m21 = (mat.$matrix.m21 * this.$matrix.m11 + mat.$matrix.m22 * this.$matrix.m21
               + mat.$matrix.m23 * this.$matrix.m31 + mat.$matrix.m24 * this.$matrix.m41);
    var m22 = (mat.$matrix.m21 * this.$matrix.m12 + mat.$matrix.m22 * this.$matrix.m22
               + mat.$matrix.m23 * this.$matrix.m32 + mat.$matrix.m24 * this.$matrix.m42);
    var m23 = (mat.$matrix.m21 * this.$matrix.m13 + mat.$matrix.m22 * this.$matrix.m23
               + mat.$matrix.m23 * this.$matrix.m33 + mat.$matrix.m24 * this.$matrix.m43);
    var m24 = (mat.$matrix.m21 * this.$matrix.m14 + mat.$matrix.m22 * this.$matrix.m24
               + mat.$matrix.m23 * this.$matrix.m34 + mat.$matrix.m24 * this.$matrix.m44);

    var m31 = (mat.$matrix.m31 * this.$matrix.m11 + mat.$matrix.m32 * this.$matrix.m21
               + mat.$matrix.m33 * this.$matrix.m31 + mat.$matrix.m34 * this.$matrix.m41);
    var m32 = (mat.$matrix.m31 * this.$matrix.m12 + mat.$matrix.m32 * this.$matrix.m22
               + mat.$matrix.m33 * this.$matrix.m32 + mat.$matrix.m34 * this.$matrix.m42);
    var m33 = (mat.$matrix.m31 * this.$matrix.m13 + mat.$matrix.m32 * this.$matrix.m23
               + mat.$matrix.m33 * this.$matrix.m33 + mat.$matrix.m34 * this.$matrix.m43);
    var m34 = (mat.$matrix.m31 * this.$matrix.m14 + mat.$matrix.m32 * this.$matrix.m24
               + mat.$matrix.m33 * this.$matrix.m34 + mat.$matrix.m34 * this.$matrix.m44);

    var m41 = (mat.$matrix.m41 * this.$matrix.m11 + mat.$matrix.m42 * this.$matrix.m21
               + mat.$matrix.m43 * this.$matrix.m31 + mat.$matrix.m44 * this.$matrix.m41);
    var m42 = (mat.$matrix.m41 * this.$matrix.m12 + mat.$matrix.m42 * this.$matrix.m22
               + mat.$matrix.m43 * this.$matrix.m32 + mat.$matrix.m44 * this.$matrix.m42);
    var m43 = (mat.$matrix.m41 * this.$matrix.m13 + mat.$matrix.m42 * this.$matrix.m23
               + mat.$matrix.m43 * this.$matrix.m33 + mat.$matrix.m44 * this.$matrix.m43);
    var m44 = (mat.$matrix.m41 * this.$matrix.m14 + mat.$matrix.m42 * this.$matrix.m24
               + mat.$matrix.m43 * this.$matrix.m34 + mat.$matrix.m44 * this.$matrix.m44);

    this.$matrix.m11 = m11;
    this.$matrix.m12 = m12;
    this.$matrix.m13 = m13;
    this.$matrix.m14 = m14;

    this.$matrix.m21 = m21;
    this.$matrix.m22 = m22;
    this.$matrix.m23 = m23;
    this.$matrix.m24 = m24;

    this.$matrix.m31 = m31;
    this.$matrix.m32 = m32;
    this.$matrix.m33 = m33;
    this.$matrix.m34 = m34;

    this.$matrix.m41 = m41;
    this.$matrix.m42 = m42;
    this.$matrix.m43 = m43;
    this.$matrix.m44 = m44;
}

J3DIMatrix4.prototype.divide = function(divisor)
{
    this.$matrix.m11 /= divisor;
    this.$matrix.m12 /= divisor;
    this.$matrix.m13 /= divisor;
    this.$matrix.m14 /= divisor;

    this.$matrix.m21 /= divisor;
    this.$matrix.m22 /= divisor;
    this.$matrix.m23 /= divisor;
    this.$matrix.m24 /= divisor;

    this.$matrix.m31 /= divisor;
    this.$matrix.m32 /= divisor;
    this.$matrix.m33 /= divisor;
    this.$matrix.m34 /= divisor;

    this.$matrix.m41 /= divisor;
    this.$matrix.m42 /= divisor;
    this.$matrix.m43 /= divisor;
    this.$matrix.m44 /= divisor;

}

J3DIMatrix4.prototype.ortho = function(left, right, bottom, top, near, far)
{
    var tx = (left + right) / (left - right);
    var ty = (top + bottom) / (top - bottom);
    var tz = (far + near) / (far - near);

    var matrix = new J3DIMatrix4();
    matrix.$matrix.m11 = 2 / (left - right);
    matrix.$matrix.m12 = 0;
    matrix.$matrix.m13 = 0;
    matrix.$matrix.m14 = 0;
    matrix.$matrix.m21 = 0;
    matrix.$matrix.m22 = 2 / (top - bottom);
    matrix.$matrix.m23 = 0;
    matrix.$matrix.m24 = 0;
    matrix.$matrix.m31 = 0;
    matrix.$matrix.m32 = 0;
    matrix.$matrix.m33 = -2 / (far - near);
    matrix.$matrix.m34 = 0;
    matrix.$matrix.m41 = tx;
    matrix.$matrix.m42 = ty;
    matrix.$matrix.m43 = tz;
    matrix.$matrix.m44 = 1;

    this.multiply(matrix);
}

J3DIMatrix4.prototype.frustum = function(left, right, bottom, top, near, far)
{
    var matrix = new J3DIMatrix4();
    var A = (right + left) / (right - left);
    var B = (top + bottom) / (top - bottom);
    var C = -(far + near) / (far - near);
    var D = -(2 * far * near) / (far - near);

    matrix.$matrix.m11 = (2 * near) / (right - left);
    matrix.$matrix.m12 = 0;
    matrix.$matrix.m13 = 0;
    matrix.$matrix.m14 = 0;

    matrix.$matrix.m21 = 0;
    matrix.$matrix.m22 = 2 * near / (top - bottom);
    matrix.$matrix.m23 = 0;
    matrix.$matrix.m24 = 0;

    matrix.$matrix.m31 = A;
    matrix.$matrix.m32 = B;
    matrix.$matrix.m33 = C;
    matrix.$matrix.m34 = -1;

    matrix.$matrix.m41 = 0;
    matrix.$matrix.m42 = 0;
    matrix.$matrix.m43 = D;
    matrix.$matrix.m44 = 0;

    this.multiply(matrix);
}

J3DIMatrix4.prototype.perspective = function(fovy, aspect, zNear, zFar)
{
    var top = Math.tan(fovy * Math.PI / 360) * zNear;
    var bottom = -top;
    var left = aspect * bottom;
    var right = aspect * top;
    this.frustum(left, right, bottom, top, zNear, zFar);
}

J3DIMatrix4.prototype.lookat = function(eyex, eyey, eyez, centerx, centery, centerz, upx, upy, upz)
{
    if (typeof eyez == 'object' && "length" in eyez) {
        var t = eyez;
        upx = t[0];
        upy = t[1];
        upz = t[2];

        t = eyey;
        centerx = t[0];
        centery = t[1];
        centerz = t[2];

        t = eyex;
        eyex = t[0];
        eyey = t[1];
        eyez = t[2];
    }

    var matrix = new J3DIMatrix4();

    // Make rotation matrix

    // Z vector
    var zx = eyex - centerx;
    var zy = eyey - centery;
    var zz = eyez - centerz;
    var mag = Math.sqrt(zx * zx + zy * zy + zz * zz);
    if (mag) {
        zx /= mag;
        zy /= mag;
        zz /= mag;
    }

    // Y vector
    var yx = upx;
    var yy = upy;
    var yz = upz;

    // X vector = Y cross Z
    xx =  yy * zz - yz * zy;
    xy = -yx * zz + yz * zx;
    xz =  yx * zy - yy * zx;

    // Recompute Y = Z cross X
    yx = zy * xz - zz * xy;
    yy = -zx * xz + zz * xx;
    yx = zx * xy - zy * xx;

    // cross product gives area of parallelogram, which is < 1.0 for
    // non-perpendicular unit-length vectors; so normalize x, y here

    mag = Math.sqrt(xx * xx + xy * xy + xz * xz);
    if (mag) {
        xx /= mag;
        xy /= mag;
        xz /= mag;
    }

    mag = Math.sqrt(yx * yx + yy * yy + yz * yz);
    if (mag) {
        yx /= mag;
        yy /= mag;
        yz /= mag;
    }

    matrix.$matrix.m11 = xx;
    matrix.$matrix.m12 = xy;
    matrix.$matrix.m13 = xz;
    matrix.$matrix.m14 = 0;

    matrix.$matrix.m21 = yx;
    matrix.$matrix.m22 = yy;
    matrix.$matrix.m23 = yz;
    matrix.$matrix.m24 = 0;

    matrix.$matrix.m31 = zx;
    matrix.$matrix.m32 = zy;
    matrix.$matrix.m33 = zz;
    matrix.$matrix.m34 = 0;

    matrix.$matrix.m41 = 0;
    matrix.$matrix.m42 = 0;
    matrix.$matrix.m43 = 0;
    matrix.$matrix.m44 = 1;
    matrix.translate(-eyex, -eyey, -eyez);

    this.multiply(matrix);
}

// Returns true on success, false otherwise. All params are Array objects
J3DIMatrix4.prototype.decompose = function(_translate, _rotate, _scale, _skew, _perspective)
{
    // Normalize the matrix.
    if (this.$matrix.m44 == 0)
        return false;

    // Gather the params
    var translate, rotate, scale, skew, perspective;

    var translate = (_translate == undefined || !("length" in _translate)) ? new J3DIVector3 : _translate;
    var rotate = (_rotate == undefined || !("length" in _rotate)) ? new J3DIVector3 : _rotate;
    var scale = (_scale == undefined || !("length" in _scale)) ? new J3DIVector3 : _scale;
    var skew = (_skew == undefined || !("length" in _skew)) ? new J3DIVector3 : _skew;
    var perspective = (_perspective == undefined || !("length" in _perspective)) ? new Array(4) : _perspective;

    var matrix = new J3DIMatrix4(this);

    matrix.divide(matrix.$matrix.m44);

    // perspectiveMatrix is used to solve for perspective, but it also provides
    // an easy way to test for singularity of the upper 3x3 component.
    var perspectiveMatrix = new J3DIMatrix4(matrix);

    perspectiveMatrix.$matrix.m14 = 0;
    perspectiveMatrix.$matrix.m24 = 0;
    perspectiveMatrix.$matrix.m34 = 0;
    perspectiveMatrix.$matrix.m44 = 1;

    if (perspectiveMatrix._determinant4x4() == 0)
        return false;

    // First, isolate perspective.
    if (matrix.$matrix.m14 != 0 || matrix.$matrix.m24 != 0 || matrix.$matrix.m34 != 0) {
        // rightHandSide is the right hand side of the equation.
        var rightHandSide = [ matrix.$matrix.m14, matrix.$matrix.m24, matrix.$matrix.m34, matrix.$matrix.m44 ];

        // Solve the equation by inverting perspectiveMatrix and multiplying
        // rightHandSide by the inverse.
        var inversePerspectiveMatrix = new J3DIMatrix4(perspectiveMatrix);
        inversePerspectiveMatrix.invert();
        var transposedInversePerspectiveMatrix = new J3DIMatrix4(inversePerspectiveMatrix);
        transposedInversePerspectiveMatrix.transpose();
        transposedInversePerspectiveMatrix.multVecMatrix(perspective, rightHandSide);

        // Clear the perspective partition
        matrix.$matrix.m14 = matrix.$matrix.m24 = matrix.$matrix.m34 = 0
        matrix.$matrix.m44 = 1;
    }
    else {
        // No perspective.
        perspective[0] = perspective[1] = perspective[2] = 0;
        perspective[3] = 1;
    }

    // Next take care of translation
    translate[0] = matrix.$matrix.m41
    matrix.$matrix.m41 = 0
    translate[1] = matrix.$matrix.m42
    matrix.$matrix.m42 = 0
    translate[2] = matrix.$matrix.m43
    matrix.$matrix.m43 = 0

    // Now get scale and shear. 'row' is a 3 element array of 3 component vectors
    var row0 = new J3DIVector3(matrix.$matrix.m11, matrix.$matrix.m12, matrix.$matrix.m13);
    var row1 = new J3DIVector3(matrix.$matrix.m21, matrix.$matrix.m22, matrix.$matrix.m23);
    var row2 = new J3DIVector3(matrix.$matrix.m31, matrix.$matrix.m32, matrix.$matrix.m33);

    // Compute X scale factor and normalize first row.
    scale[0] = row0.vectorLength();
    row0.divide(scale[0]);

    // Compute XY shear factor and make 2nd row orthogonal to 1st.
    skew[0] = row0.dot(row1);
    row1.combine(row0, 1.0, -skew[0]);

    // Now, compute Y scale and normalize 2nd row.
    scale[1] = row1.vectorLength();
    row1.divide(scale[1]);
    skew[0] /= scale[1];

    // Compute XZ and YZ shears, orthogonalize 3rd row
    skew[1] = row1.dot(row2);
    row2.combine(row0, 1.0, -skew[1]);
    skew[2] = row1.dot(row2);
    row2.combine(row1, 1.0, -skew[2]);

    // Next, get Z scale and normalize 3rd row.
    scale[2] = row2.vectorLength();
    row2.divide(scale[2]);
    skew[1] /= scale[2];
    skew[2] /= scale[2];

    // At this point, the matrix (in rows) is orthonormal.
    // Check for a coordinate system flip.  If the determinant
    // is -1, then negate the matrix and the scaling factors.
    var pdum3 = new J3DIVector3(row1);
    pdum3.cross(row2);
    if (row0.dot(pdum3) < 0) {
        for (i = 0; i < 3; i++) {
            scale[i] *= -1;
            row[0][i] *= -1;
            row[1][i] *= -1;
            row[2][i] *= -1;
        }
    }

    // Now, get the rotations out
    rotate[1] = Math.asin(-row0[2]);
    if (Math.cos(rotate[1]) != 0) {
        rotate[0] = Math.atan2(row1[2], row2[2]);
        rotate[2] = Math.atan2(row0[1], row0[0]);
    }
    else {
        rotate[0] = Math.atan2(-row2[0], row1[1]);
        rotate[2] = 0;
    }

    // Convert rotations to degrees
    var rad2deg = 180 / Math.PI;
    rotate[0] *= rad2deg;
    rotate[1] *= rad2deg;
    rotate[2] *= rad2deg;

    return true;
}

J3DIMatrix4.prototype._determinant2x2 = function(a, b, c, d)
{
    return a * d - b * c;
}

J3DIMatrix4.prototype._determinant3x3 = function(a1, a2, a3, b1, b2, b3, c1, c2, c3)
{
    return a1 * this._determinant2x2(b2, b3, c2, c3)
         - b1 * this._determinant2x2(a2, a3, c2, c3)
         + c1 * this._determinant2x2(a2, a3, b2, b3);
}

J3DIMatrix4.prototype._determinant4x4 = function()
{
    var a1 = this.$matrix.m11;
    var b1 = this.$matrix.m12;
    var c1 = this.$matrix.m13;
    var d1 = this.$matrix.m14;

    var a2 = this.$matrix.m21;
    var b2 = this.$matrix.m22;
    var c2 = this.$matrix.m23;
    var d2 = this.$matrix.m24;

    var a3 = this.$matrix.m31;
    var b3 = this.$matrix.m32;
    var c3 = this.$matrix.m33;
    var d3 = this.$matrix.m34;

    var a4 = this.$matrix.m41;
    var b4 = this.$matrix.m42;
    var c4 = this.$matrix.m43;
    var d4 = this.$matrix.m44;

    return a1 * this._determinant3x3(b2, b3, b4, c2, c3, c4, d2, d3, d4)
         - b1 * this._determinant3x3(a2, a3, a4, c2, c3, c4, d2, d3, d4)
         + c1 * this._determinant3x3(a2, a3, a4, b2, b3, b4, d2, d3, d4)
         - d1 * this._determinant3x3(a2, a3, a4, b2, b3, b4, c2, c3, c4);
}

J3DIMatrix4.prototype._makeAdjoint = function()
{
    var a1 = this.$matrix.m11;
    var b1 = this.$matrix.m12;
    var c1 = this.$matrix.m13;
    var d1 = this.$matrix.m14;

    var a2 = this.$matrix.m21;
    var b2 = this.$matrix.m22;
    var c2 = this.$matrix.m23;
    var d2 = this.$matrix.m24;

    var a3 = this.$matrix.m31;
    var b3 = this.$matrix.m32;
    var c3 = this.$matrix.m33;
    var d3 = this.$matrix.m34;

    var a4 = this.$matrix.m41;
    var b4 = this.$matrix.m42;
    var c4 = this.$matrix.m43;
    var d4 = this.$matrix.m44;

    // Row column labeling reversed since we transpose rows & columns
    this.$matrix.m11  =   this._determinant3x3(b2, b3, b4, c2, c3, c4, d2, d3, d4);
    this.$matrix.m21  = - this._determinant3x3(a2, a3, a4, c2, c3, c4, d2, d3, d4);
    this.$matrix.m31  =   this._determinant3x3(a2, a3, a4, b2, b3, b4, d2, d3, d4);
    this.$matrix.m41  = - this._determinant3x3(a2, a3, a4, b2, b3, b4, c2, c3, c4);

    this.$matrix.m12  = - this._determinant3x3(b1, b3, b4, c1, c3, c4, d1, d3, d4);
    this.$matrix.m22  =   this._determinant3x3(a1, a3, a4, c1, c3, c4, d1, d3, d4);
    this.$matrix.m32  = - this._determinant3x3(a1, a3, a4, b1, b3, b4, d1, d3, d4);
    this.$matrix.m42  =   this._determinant3x3(a1, a3, a4, b1, b3, b4, c1, c3, c4);

    this.$matrix.m13  =   this._determinant3x3(b1, b2, b4, c1, c2, c4, d1, d2, d4);
    this.$matrix.m23  = - this._determinant3x3(a1, a2, a4, c1, c2, c4, d1, d2, d4);
    this.$matrix.m33  =   this._determinant3x3(a1, a2, a4, b1, b2, b4, d1, d2, d4);
    this.$matrix.m43  = - this._determinant3x3(a1, a2, a4, b1, b2, b4, c1, c2, c4);

    this.$matrix.m14  = - this._determinant3x3(b1, b2, b3, c1, c2, c3, d1, d2, d3);
    this.$matrix.m24  =   this._determinant3x3(a1, a2, a3, c1, c2, c3, d1, d2, d3);
    this.$matrix.m34  = - this._determinant3x3(a1, a2, a3, b1, b2, b3, d1, d2, d3);
    this.$matrix.m44  =   this._determinant3x3(a1, a2, a3, b1, b2, b3, c1, c2, c3);
}

//
// J3DIVector3
//
J3DIVector3 = function(x,y,z)
{
    this.load(x,y,z);
}

J3DIVector3.prototype.load = function(x,y,z)
{
    if (typeof x == 'object' && "length" in x) {
        this[0] = x[0];
        this[1] = x[1];
        this[2] = x[2];
    }
    else if (typeof x == 'number') {
        this[0] = x;
        this[1] = y;
        this[2] = z;
    }
    else {
        this[0] = 0;
        this[1] = 0;
        this[2] = 0;
    }
}

J3DIVector3.prototype.getAsArray = function()
{
    return [ this[0], this[1], this[2] ];
}

J3DIVector3.prototype.getAsFloat32Array = function()
{
    return new Float32Array(this.getAsArray());
}

J3DIVector3.prototype.vectorLength = function()
{
    return Math.sqrt(this[0] * this[0] + this[1] * this[1] + this[2] * this[2]);
}

J3DIVector3.prototype.divide = function(divisor)
{
    this[0] /= divisor; this[1] /= divisor; this[2] /= divisor;
}

J3DIVector3.prototype.cross = function(v)
{
    this[0] =  this[1] * v[2] - this[2] * v[1];
    this[1] = -this[0] * v[2] + this[2] * v[0];
    this[2] =  this[0] * v[1] - this[1] * v[0];
}

J3DIVector3.prototype.dot = function(v)
{
    return this[0] * v[0] + this[1] * v[1] + this[2] * v[2];
}

J3DIVector3.prototype.combine = function(v, ascl, bscl)
{
    this[0] = (ascl * this[0]) + (bscl * v[0]);
    this[1] = (ascl * this[1]) + (bscl * v[1]);
    this[2] = (ascl * this[2]) + (bscl * v[2]);
}

J3DIVector3.prototype.multVecMatrix = function(matrix)
{
    var x = this[0];
    var y = this[1];
    var z = this[2];

    this[0] = matrix.$matrix.m41 + x * matrix.$matrix.m11 + y * matrix.$matrix.m21 + z * matrix.$matrix.m31;
    this[1] = matrix.$matrix.m42 + x * matrix.$matrix.m12 + y * matrix.$matrix.m22 + z * matrix.$matrix.m32;
    this[2] = matrix.$matrix.m43 + x * matrix.$matrix.m13 + y * matrix.$matrix.m23 + z * matrix.$matrix.m33;
    var w = matrix.$matrix.m44 + x * matrix.$matrix.m14 + y * matrix.$matrix.m24 + z * matrix.$matrix.m34;
    if (w != 1 && w != 0) {
        this[0] /= w;
        this[1] /= w;
        this[2] /= w;
    }
}

J3DIVector3.prototype.toString = function()
{
    return "["+this[0]+","+this[1]+","+this[2]+"]";
}
"""

LOADER = """
// TODO: header

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

RENDERER = """

var tmptexture;

function BasicRenderer(params) {

  var canvas = document.getElementById(params['canvas id']);

  // Init OpenGL.
  this.gl = null;
  try { this.gl = canvas.getContext("moz-webgl"); }
  catch (e) { }
  try { if (!this.gl) this.gl = canvas.getContext("webkit-3d"); }
  catch (e) { }
  if (!this.gl) {
    return;
  }

  // Init shaders.
  this.gl.program = this.gl.createProgram();
  this.gl.attachShader(this.gl.program, this.getShader(params['vertex program id']));
  this.gl.attachShader(this.gl.program, this.getShader(params['fragment program id']));
  var attributes = params['vertex attribute names'];
  for (var i in attributes) {
    this.gl.bindAttribLocation (this.gl.program, parseInt(i), attributes[i]);
  }
  this.gl.linkProgram(this.gl.program);
  var linked = this.gl.getProgramParameter(this.gl.program, this.gl.LINK_STATUS);
  if (!linked) {
    var error = this.gl.getProgramInfoLog (this.gl.program);
    alert("Error linking program: " + error);
    this.gl.deleteProgram(this.gl.program);
    this.gl.deleteProgram(fragmentShader);
    this.gl.deleteProgram(vertexShader);
    return null;
  }
  this.gl.useProgram(this.gl.program);

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

  // Shader variable locations and local matrices.
  this.gl.uniform3f(this.gl.getUniformLocation(
    this.gl.program, params['light variable']
  ), 0, 0, 1);
  this.gl.uniform1i(this.gl.getUniformLocation(
    this.gl.program, params['sampler2d variable']
  ), 0);
  this.gl.enable(this.gl.TEXTURE_2D);
  this.gl.mvMatrix = new J3DIMatrix4();
  this.gl.u_normalMatrixLoc = this.gl.getUniformLocation(
    this.gl.program, params['normal matrix variable']
  );
  this.gl.normalMatrix = new J3DIMatrix4();
  this.gl.u_modelViewProjMatrixLoc = this.gl.getUniformLocation(
    this.gl.program, params['mvp matrix variable']
  );
  this.gl.mvpMatrix = new J3DIMatrix4();
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

BasicRenderer.prototype.reshape = function(width, height) {
  var wd2 = width / 2.0;
  var hd2 = height / 2.0;
  this.gl.viewport(0-wd2, hd2, wd2, 0-hd2);
  //this.gl.viewport(0, 0, width, height);
  this.gl.perspectiveMatrix = new J3DIMatrix4();
  this.gl.perspectiveMatrix.perspective(30, width/height, 1, 10000);
  this.gl.perspectiveMatrix.lookat(0, 0, 7, 0, 0, 0, 0, 1, 0);
  this.gl.mvMatrix.makeIdentity();
  this.gl.mvMatrix.translate(0,-1,0);
  this.gl.mvMatrix.rotate(-65, 1,0,0);
  this.gl.normalMatrix.load(this.gl.mvMatrix);
  this.gl.normalMatrix.invert();
  this.gl.normalMatrix.transpose();
  this.gl.normalMatrix.setUniform(this.gl, this.gl.u_normalMatrixLoc, false);
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
  gl.bindTexture(gl.TEXTURE_2D, null);
  //gl.generateMipmap(gl.TEXTURE_2D);
  return texture;
}

BasicRenderer.prototype.standardVBO = function(data, args) {

  var gl = args[0];
  var vbo = new StandardVBO();

  /*if (
    !data["vertices"] ||
    !data["normals"] ||
    !data["texcoords"] ||
    !data["indices"]
  ) {
    return vbo;
  }*/

  // Create vertex VBO.
  vbo.vertexData = data["vertices"];
  vbo.vertices = new Float32Array(vbo.vertexData);
  vbo.vertexObject = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo.vertexObject);
  gl.bufferData(gl.ARRAY_BUFFER, vbo.vertices, gl.STATIC_DRAW);

  // Create normals VBO.
  vbo.normalsData = data["normals"];
  vbo.normals = new Float32Array(vbo.normalsData);
  vbo.normalsObject = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo.normalsObject);
  gl.bufferData(gl.ARRAY_BUFFER, vbo.normals, gl.STATIC_DRAW);

  // Create texcoords VBO.
  vbo.texcoordsData = data["texcoords"];
  if (vbo.texcoordsData) {
    vbo.texcoords = new Float32Array(vbo.texcoordsData);
    vbo.texcoordsObject = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo.texcoordsObject);
    gl.bufferData(gl.ARRAY_BUFFER, vbo.texcoords, gl.STATIC_DRAW);
  }
  else {
    vbo.texcoordsObject = null;
  }

  gl.bindBuffer(gl.ARRAY_BUFFER, null);

  // Create indices.
  vbo.indicesData = data["indices"];
  vbo.indices = new Uint16Array(vbo.indicesData);
  vbo.indicesObject = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, vbo.indicesObject);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, vbo.indices, gl.STATIC_DRAW);

  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, null);

  // Accounting.
  vbo.vertexCount = vbo.indicesData.length;
  vbo.complete = true;

  //alert(vbo.vertexCount + ' complete');

  return vbo;
}

BasicRenderer.prototype.renderMesh = function(vbo, texture) {
  if (!vbo.bind(this.gl)) return;
  this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
  this.gl.drawElements(this.gl.TRIANGLES, vbo.vertexCount, this.gl.UNSIGNED_SHORT, 0);
  vbo.unbind(this.gl);
}

BasicRenderer.prototype.render = function(scene) {
  this.gl.clear(this.gl.COLOR_BUFFER_BIT | this.gl.DEPTH_BUFFER_BIT);
  this.gl.mvMatrix.rotate(.5, 0,0,1);
  for (i in scene.meshes) {
    if (i == 'Cylinder_016') continue;
    var mesh = scene.meshes[i];
    this.gl.mvpMatrix.load(this.gl.perspectiveMatrix);
    this.gl.mvpMatrix.multiply(this.gl.mvMatrix);
    if (!mesh.modelMatrix) {
      mesh.modelMatrix = new J3DIMatrix4();
      mesh.modelMatrix.translate(mesh.translate[0], mesh.translate[1], mesh.translate[2])
      mesh.modelMatrix.rotate(mesh.rotate[2], 0.0, 0.0, 1.0);
      mesh.modelMatrix.rotate(mesh.rotate[1], 0.0, 1.0, 0.0);
      mesh.modelMatrix.rotate(mesh.rotate[0], 1.0, 0.0, 0.0);
      mesh.modelMatrix.scale(mesh.scale[0], mesh.scale[1], mesh.scale[2])
      mesh.texture = scene.textures[mesh.textureID];
    }
    this.gl.mvpMatrix.multiply(mesh.modelMatrix);
    this.gl.mvpMatrix.setUniform(this.gl, this.gl.u_modelViewProjMatrixLoc, false);
    this.renderMesh(mesh.vbo, mesh.texture);
  }
}

function StandardVBO() {
  this.complete = false;
}

StandardVBO.prototype.bind = function(gl) {
  //if (!this.complete) return false;
  gl.bindBuffer(gl.ARRAY_BUFFER, this.vertexObject);
  gl.vertexAttribPointer(2, 3, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, this.normalsObject);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, this.texcoordsObject);
  gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indicesObject);
  return true;
}

StandardVBO.prototype.unbind = function(gl) {
  if (!this.complete) return;
  gl.bindBuffer(gl.ARRAY_BUFFER, null);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, null);
}

"""

HTML = """
<html>
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
      #canvas3d {
        padding-left: 1px; /* unsure why this is needed for minefield */
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
    <script type='text/javascript' src='js/J3DIMath.js'></script>
    <script type='text/javascript' src='js/webgl-jso-jqueryloader.js'></script>
    <script type='text/javascript' src='js/webgl-jso-basicrenderer.js'></script>
    <script type='text/javascript' src='js/board.js'></script>
    <script id='vprog' type='x-shader/x-vertex'>
      uniform mat4 u_modelViewProjMatrix;
      uniform mat4 u_normalMatrix;
      uniform vec3 lightDir;
      attribute vec3 vNormal;
      attribute vec2 vTexCoord;
      attribute vec4 vPosition;
      varying float v_Dot;
      varying vec2 v_texCoord;
      void main() {
        gl_Position = u_modelViewProjMatrix * vPosition;
        v_texCoord = vTexCoord.st;
        vec4 transNormal = u_normalMatrix * vec4(vNormal, 1);
        v_Dot = max(dot(transNormal.xyz, lightDir), 0.0);
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
        color += vec4(0.2, 0.2, 0.2, 1.0);
        gl_FragColor = vec4(color.xyz * v_Dot, color.a);
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
        'mvp matrix variable': 'u_modelViewProjMatrix',
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
          'vbo arguments': [ renderer.gl ]
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
            renderer.reshape(canvas.width(), canvas.height());
            setInterval(function() {
              // Main loop.
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
