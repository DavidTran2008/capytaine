#!/usr/bin/env python
#  -*- coding: utf-8 -*-
"""Functions to load meshes from different file formats.
Based on meshmagick <https://github.com/LHEEA/meshmagick> by François Rongère.
"""
# Copyright (C) 2017-2019 Matthieu Ancellin, based on the work of François Rongère
# See LICENSE file at <https://github.com/mancellin/capytaine>

import os
import numpy as np

from capytaine.meshes.meshes import Mesh
from capytaine.meshes.symmetric import ReflectionSymmetricMesh
from capytaine.meshes.geometry import xOz_Plane

real_str = r'[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][+-]?\d+)?'  # Regex for floats


def _check_file(filename, name=None):
    if not os.path.isfile(filename):
        raise IOError("file %s not found" % filename)
    return


def load_mesh(filename, file_format=None, name=None):
    """Driver function that loads every mesh file format known by meshmagick.
    Dispatch to one of the other function depending on file_format.

    Parameters
    ----------
    filename: str
        name of the meh file on disk
    file_format: str, optional
        format of the mesh defined in the extension_dict dictionary
    name: str, optional
        name for the created mesh object

    Returns
    -------
    Mesh or SymmetricMesh
        the loaded mesh
    """
    _check_file(filename)

    if file_format is None:
        _, file_format = os.path.splitext(filename)
        file_format = file_format.strip('.')

    if file_format not in extension_dict:
        raise IOError('Extension ".%s" is not known' % file_format)

    loader = extension_dict[file_format]

    return loader(filename, name)


def load_RAD(filename, name=None):
    """Loads RADIOSS mesh files. This export file format may be chosen in ICEM meshing program.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    RAD files have a 1-indexing
    """

    import re
    _check_file(filename)
    ifile = open(filename, 'r')
    data = ifile.read()
    ifile.close()

    # node_line = r'\s*\d+(?:\s*' + real_str + '){3}'
    node_line = r'\s*\d+\s*(' + real_str + r')\s*(' + real_str + r')\s*(' + real_str + ')'
    node_section = r'((?:' + node_line + ')+)'

    elem_line = r'^\s*(?:\d+\s+){6}\d+\s*[\r\n]+'
    elem_section = r'((?:' + elem_line + '){3,})'

    pattern_node_line = re.compile(node_line, re.MULTILINE)
    # pattern_node_line_group = re.compile(node_line, re.MULTILINE)
    pattern_elem_line = re.compile(elem_line, re.MULTILINE)
    pattern_node_section = re.compile(node_section, re.MULTILINE)
    pattern_elem_section = re.compile(elem_section, re.MULTILINE)

    vertices = []
    node_section = pattern_node_section.search(data).group(1)
    for node in pattern_node_line.finditer(node_section):
        vertices.append(list(map(float, list(node.groups()))))
    vertices = np.asarray(vertices, dtype=float)

    faces = []
    elem_section = pattern_elem_section.search(data).group(1)
    for elem in pattern_elem_line.findall(elem_section):
        faces.append(list(map(int, elem.strip().split()[3:])))
    faces = np.asarray(faces, dtype=np.int) - 1

    return Mesh(vertices, faces, name)


def load_HST(filename, name=None):
    """Loads HYDROSTAR (Bureau Veritas (c)) mesh files.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    HST files have a 1-indexing
    """
    _check_file(filename)

    ifile = open(filename, 'r')
    data = ifile.read()
    ifile.close()

    import re

    node_line = r'\s*\d+(?:\s+' + real_str + '){3}'
    node_section = r'((?:' + node_line + ')+)'

    elem_line = r'^\s*(?:\d+\s+){3}\d+\s*[\r\n]+'
    elem_section = r'((?:' + elem_line + ')+)'

    pattern_node_line = re.compile(node_line, re.MULTILINE)
    pattern_elem_line = re.compile(elem_line, re.MULTILINE)
    pattern_node_section = re.compile(node_section, re.MULTILINE)
    pattern_elem_section = re.compile(elem_section, re.MULTILINE)

    vertices_tmp = []
    vertices = []
    nv = 0
    for node_section in pattern_node_section.findall(data):
        for node in pattern_node_line.findall(node_section):
            vertices_tmp.append(list(map(float, node.split()[1:])))
        nv_tmp = len(vertices_tmp)
        vertices_tmp = np.asarray(vertices_tmp, dtype=np.float)
        if nv == 0:
            vertices = vertices_tmp.copy()
            nv = nv_tmp
        else:
            vertices = np.concatenate((vertices, vertices_tmp))
            nv += nv_tmp

    faces_tmp = []
    faces = []
    nf = 0
    for elem_section in pattern_elem_section.findall(data):
        for elem in pattern_elem_line.findall(elem_section):
            faces_tmp.append(list(map(int, elem.split())))
        nf_tmp = len(faces_tmp)
        faces_tmp = np.asarray(faces_tmp, dtype=np.int)
        if nf == 0:
            faces = faces_tmp.copy()
            nf = nf_tmp
        else:
            faces = np.concatenate((faces, faces_tmp))
            nf += nf_tmp

    return Mesh(vertices, faces-1, name)


def load_DAT(filename, name=None):
    """Not implemented.
    Intended to load .DAT files used in DIODORE (PRINCIPIA (c))
    """
    _check_file(filename)
    raise NotImplementedError


def load_INP(filename, name=None):
    """Loads DIODORE (PRINCIPIA (c)) configuration file format.

    It parses the .INP file and extract meshes defined in subsequent .DAT files using the different informations
    contained in the .INP file.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    INP/DAT files use a 1-indexing
    """
    _check_file(filename)
    import re

    with open(filename, 'r') as f:
        text = f.read()

    # Retrieving frames into a dictionnary frames
    pattern_frame_str = r'^\s*\*FRAME,NAME=(.+)[\r\n]+(.*)'
    pattern_frame = re.compile(pattern_frame_str, re.MULTILINE)

    frames = {}
    for match in pattern_frame.finditer(text):
        frame_name = match.group(1).strip()
        frame_vector = re.split(r'[, ]', match.group(2).strip())
        frames[frame_name] = np.asarray(list(map(float, frame_vector)))

    # Storing the inp layout into a list of dictionary
    pattern_node_elements = re.compile(r'^\s*\*(NODE|ELEMENT),(.*)', re.MULTILINE)
    layout = []
    mesh_files = {}
    for match in pattern_node_elements.finditer(text):
        field_dict = dict()
        field_dict['type'] = match.group(1)
        if field_dict['type'] == 'NODE':
            field_dict['INCREMENT'] = 'NO'
        opts = match.group(2).split(',')
        for opt in opts:
            key, pair = opt.split('=')
            field_dict[key] = pair.strip()

        # Retrieving information on mesh files and their usage
        file = field_dict['INPUT']
        if file in mesh_files:
            mesh_files[file][field_dict['type'] + '_CALL_INP'] += 1
        else:
            mesh_files[file] = {}
            mesh_files[file]['NODE_CALL_INP'] = 0
            mesh_files[file]['ELEMENT_CALL_INP'] = 0
            mesh_files[file][field_dict['type'] + '_CALL_INP'] += 1

        layout.append(field_dict)

        # RETRIEVING DATA SECTIONS FROM MESHFILES
        # patterns for recognition of sections
    node_line = r'\s*\d+(?:\s+' + real_str + '){3}'
    node_section = r'((?:' + node_line + ')+)'
    elem_line = r'^ +\d+(?: +\d+){3,4}[\r\n]+'  # 3 -> triangle, 4 -> quadrangle
    elem_section = r'((?:' + elem_line + ')+)'
    pattern_node_line = re.compile(node_line, re.MULTILINE)
    pattern_elem_line = re.compile(elem_line, re.MULTILINE)
    pattern_node_section = re.compile(node_section, re.MULTILINE)
    pattern_elem_section = re.compile(elem_section, re.MULTILINE)

    for file in mesh_files:
        try:
            meshfile = open(os.path.join(os.path.dirname(filename), file + '.DAT'), 'r')
        except:
            raise IOError('File {0:s} not found'.format(file + '.DAT'))
        data = meshfile.read()
        meshfile.close()

        node_section = pattern_node_section.findall(data)
        if len(node_section) > 1:
            raise IOError("""Several NODE sections into a .DAT file is not supported by meshmagick
                              as it is considered as bad practice""")
        node_array = []
        idx_array = []
        for node in pattern_node_line.findall(node_section[0]):
            node = node.split()

            node[0] = int(node[0])
            idx_array.append(node[0])
            node[1:] = list(map(float, node[1:]))
            node_array.append(node[1:])

        mesh_files[file]['NODE_SECTION'] = node_array

        # Detecting renumberings to do
        real_idx = 0
        # renumberings = []
        id_new = - np.ones(max(idx_array) + 1, dtype=np.int)
        # FIXME: cette partie est tres buggee !!!
        for i, idx in enumerate(idx_array):
            id_new[idx] = i+1

        mesh_files[file]['ELEM_SECTIONS'] = []
        for elem_section in pattern_elem_section.findall(data):

            elem_array = []
            for elem in pattern_elem_line.findall(elem_section):
                elem = list(map(int, elem.split()))
                # for node in elem[1:]:
                elem = id_new[elem[1:]].tolist()
                if len(elem) == 3:  # Case of a triangle, we repeat the first node at the last position
                    elem.append(elem[0])

                elem_array.append(list(map(int, elem)))
            mesh_files[file]['ELEM_SECTIONS'].append(elem_array)
        mesh_files[file]['nb_elem_sections'] = len(mesh_files[file]['ELEM_SECTIONS'])

        mesh_files[file]['nb_elem_sections_used'] = 0

    nb_nodes = 0
    nb_elems = 0
    for field in layout:
        file = field['INPUT']
        if field['type'] == 'NODE':
            nodes = np.asarray(mesh_files[file]['NODE_SECTION'], dtype=np.float)
            # Translation of nodes according to frame option id any
            nodes += frames[field['FRAME']]  # TODO: s'assurer que frame est une options obligatoire...

            if nb_nodes == 0:
                vertices = nodes.copy()
                nb_nodes = vertices.shape[0]
                increment = False
                continue

            if field['INCREMENT'] == 'NO':
                vertices[idx, :] = nodes.copy()
                increment = False
            else:
                vertices = np.concatenate((vertices, nodes))
                nb_nodes = vertices.shape[0]
                increment = True
        else:  # this is an ELEMENT section
            elem_section = np.asarray(mesh_files[file]['ELEM_SECTIONS'][mesh_files[file]['nb_elem_sections_used']],
                                      dtype=np.int)

            mesh_files[file]['nb_elem_sections_used'] += 1
            if mesh_files[file]['nb_elem_sections_used'] == mesh_files[file]['nb_elem_sections']:
                mesh_files[file]['nb_elem_sections_used'] = 0

            # Updating to new id of nodes
            elems = elem_section
            if increment:
                elems += nb_nodes

            if nb_elems == 0:
                faces = elems.copy()
                nb_elems = faces.shape[0]
                continue
            else:
                faces = np.concatenate((faces, elems))
                nb_elems = faces.shape[0]

    return Mesh(vertices, faces-1, name)


def load_TEC(filename, name=None):
    """Loads TECPLOT (Tecplot (c)) mesh files.

    It relies on the tecplot file reader from the VTK library.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    TEC files have a 1-indexing
    """

    import re

    _check_file(filename)

    data_pattern = re.compile(
                    r'ZONE.*\s*N\s*=\s*(\d+)\s*,\s*E=\s*(\d+)\s*,\s*F\s*=\s*FEPOINT\s*,\s*ET\s*=\s*QUADRILATERAL\s+'
                    + r'(^(?:\s*' + real_str + r'){3,})\s+'
                    + r'(^(?:\s*\d+)*)', re.MULTILINE)

    with open(filename, 'r') as f:
        data = f.read()

    nv, nf, vertices, faces = data_pattern.search(data).groups()
    nv = int(nv)
    nf = int(nf)

    vertices = np.asarray(list(map(float, vertices.split())), dtype=np.float).reshape((nv, -1))[:, :3]
    faces = np.asarray(list(map(int, faces.split())), dtype=np.int).reshape((nf, 4))-1

    return Mesh(vertices, faces, name)


def load_VTU(filename, name=None):
    """Loads VTK file format in the new XML format (vtu file extension for unstructured meshes).

    It relies on the reader from the VTK library.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    VTU files have a 0-indexing
    """

    _check_file(filename)

    from vtk import vtkXMLUnstructuredGridReader
    reader = vtkXMLUnstructuredGridReader()
    reader.SetFileName(filename)
    reader.Update()
    vtk_mesh = reader.GetOutput()

    vertices, faces = _dump_vtk(vtk_mesh)
    return Mesh(vertices, faces, name)


def load_VTP(filename, name=None):
    """Loads VTK file format in the new XML format (vtp file extension for polydata meshes).

    It relies on the reader from the VTK library.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    VTP files have a 0-indexing
    """
    _check_file(filename)

    from vtk import vtkXMLPolyDataReader
    reader = vtkXMLPolyDataReader()
    reader.SetFileName(filename)
    reader.Update()
    vtk_mesh = reader.GetOutput()

    vertices, faces = _dump_vtk(vtk_mesh)
    return Mesh(vertices, faces, name)


def load_VTK(filename, name=None):
    """Loads VTK file format in the legacy format (vtk file extension).

    It relies on the reader from the VTK library.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    VTU files have a 0-indexing
    """
    _check_file(filename)

    from vtk import vtkPolyDataReader
    reader = vtkPolyDataReader()
    reader.SetFileName(filename)
    reader.Update()
    vtk_mesh = reader.GetOutput()

    vertices, faces = _dump_vtk(vtk_mesh)
    return Mesh(vertices, faces, name)


def _dump_vtk(vtk_mesh):
    """Internal driver function that uses the VTK library to read VTK polydata or vtk unstructured grid data structures

    Returns
    -------
    vertices: ndarray
        numpy array of the coordinates of the mesh's nodes
    faces: ndarray
        numpy array of the faces' nodes connectivities
    """

    nv = vtk_mesh.GetNumberOfPoints()
    vertices = np.zeros((nv, 3), dtype=np.float)
    for k in range(nv):
        vertices[k] = np.array(vtk_mesh.GetPoint(k))

    nf = vtk_mesh.GetNumberOfCells()
    faces = np.zeros((nf, 4), dtype=np.int)
    for k in range(nf):
        cell = vtk_mesh.GetCell(k)
        nv_facet = cell.GetNumberOfPoints()
        for l in range(nv_facet):
            faces[k][l] = cell.GetPointId(l)
        if nv_facet == 3:
            faces[k][3] = faces[k][0]

    return vertices, faces


def load_STL(filename, name=None):
    """Loads STL file format.

    It relies on the reader from the VTK library. As STL file format maintains a redundant set of vertices for each
    faces of the mesh, it returns a merged list of nodes and connectivity array by using the merge_duplicates function.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    STL files have a 0-indexing
    """
    from vtk import vtkSTLReader
    from .tools import merge_duplicate_rows

    _check_file(filename)

    reader = vtkSTLReader()
    reader.SetFileName(filename)
    reader.Update()

    data = reader.GetOutputDataObject(0)

    nv = data.GetNumberOfPoints()
    vertices = np.zeros((nv, 3), dtype=np.float)
    for k in range(nv):
        vertices[k] = np.array(data.GetPoint(k))
    nf = data.GetNumberOfCells()
    faces = np.zeros((nf, 4), dtype=np.int)
    for k in range(nf):
        cell = data.GetCell(k)
        if cell is not None:
            for l in range(3):
                faces[k][l] = cell.GetPointId(l)
                faces[k][3] = faces[k][0]  # always repeating the first node as stl is triangle only

    # Merging duplicates nodes
    vertices, new_id = merge_duplicate_rows(vertices, return_index=True)
    faces = new_id[faces]

    return Mesh(vertices, faces, name)


def load_NAT(filename, name=None):
    """This function loads natural file format for meshes.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Notes
    -----
    The file format is as follow::

        xsym    ysym
        n    m
        x1    y1    z1
        .
        .
        .
        xn    yn    zn
        i1    j1    k1    l1
        .
        .
        .
        im    jm    km    lm

    where :
    n : number of nodes
    m : number of cells
    x1 y1 z1 : cartesian coordinates of node 1
    i1 j1 k1 l1 : counterclock wise Ids of nodes for cell 1
    if cell 1 is a triangle, i1==l1

    Note
    ----
    NAT files have a 1-indexing
    """

    _check_file(filename)

    ifile = open(filename, 'r')
    ifile.readline()
    nv, nf = list(map(int, ifile.readline().split()))

    vertices = []
    for i in range(nv):
        vertices.append(list(map(float, ifile.readline().split())))
    vertices = np.array(vertices, dtype=np.float)

    faces = []
    for i in range(nf):
        faces.append(list(map(int, ifile.readline().split())))
    faces = np.array(faces, dtype=np.int)

    ifile.close()
    return Mesh(vertices, faces-1, name)


def load_GDF(filename, name=None):
    """Loads WAMIT (Wamit INC. (c)) GDF mesh files.

    As GDF file format maintains a redundant set of vertices for each faces of the mesh, it returns a merged list of
    nodes and connectivity array by using the merge_duplicates function.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    GDF files have a 1-indexing
    """

    _check_file(filename)

    ifile = open(filename, 'r')

    ifile.readline()  # skip one header line
    line = ifile.readline().split()
    ulen = line[0]
    grav = line[1]

    line = ifile.readline().split()
    isx = line[0]
    isy = line[1]

    line = ifile.readline().split()
    nf = int(line[0])

    vertices = np.zeros((4 * nf, 3), dtype=np.float)
    faces = np.zeros((nf, 4), dtype=np.int)

    iv = -1
    for icell in range(nf):

        for k in range(4):
            iv += 1
            vertices[iv, :] = np.array(ifile.readline().split())
            faces[icell, k] = iv

    ifile.close()

    return Mesh(vertices, faces, name)


def load_MAR(filename, name=None):
    """Loads Nemoh (Ecole Centrale de Nantes) mesh files.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh or ReflectionSymmetry
        the loaded mesh

    Note
    ----
    MAR files have a 1-indexing
    """

    _check_file(filename)

    ifile = open(filename, 'r')

    header = ifile.readline()
    _, symmetric_mesh = header.split()

    vertices = []
    while 1:
        line = ifile.readline()
        line = line.split()
        if line[0] == '0':
            break
        vertices.append(list(map(float, line[1:])))

    vertices = np.array(vertices, dtype=np.float)
    faces = []
    while 1:
        line = ifile.readline()
        line = line.split()
        if line[0] == '0':
            break
        faces.append(list(map(int, line)))

    faces = np.array(faces, dtype=np.int)

    ifile.close()

    if int(symmetric_mesh) == 1:
        if name is None:
            half_mesh = Mesh(vertices, faces-1)
            return ReflectionSymmetricMesh(half_mesh, plane=xOz_Plane)
        else:
            half_mesh = Mesh(vertices, faces-1, name=f"half_of_{name}")
            return ReflectionSymmetricMesh(half_mesh, plane=xOz_Plane, name=name)
    else:
        return Mesh(vertices, faces-1, name)


def load_MSH(filename, name=None):
    """Loads .MSH mesh files generated by GMSH by C. Geuzaine and J.F. Remacle.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    MSH files have a 1-indexing
    """

    import re

    _check_file(filename)

    with open(filename, 'r') as file:
        data = file.read()

    nb_nodes, nodes_data = re.search(r'\$Nodes\n(\d+)\n(.+)\$EndNodes', data, re.DOTALL).groups()
    nb_elts, elts_data = re.search(r'\$Elements\n(\d+)\n(.+)\$EndElements', data, re.DOTALL).groups()

    vertices = np.asarray(list(map(float, nodes_data.split())), dtype=np.float).reshape((-1, 4))[:, 1:]
    vertices = np.ascontiguousarray(vertices)
    faces = []

    # Triangles
    for tri_elt in re.findall(r'(^\d+\s2(?:\s\d+)+?$)', elts_data, re.MULTILINE):
        tri_elt = list(map(int, tri_elt.split()))
        triangle = tri_elt[-3:]
        triangle.append(triangle[0])
        faces.append(triangle)

    for quad_elt in re.findall(r'(^\d+\s3(?:\s\d+)+?$)', elts_data, re.MULTILINE):
        quad_elt = list(map(int, quad_elt.split()))
        quadrangle = quad_elt[-4:]
        faces.append(quadrangle)

    faces = np.asarray(faces, dtype=np.int) - 1

    return Mesh(vertices, faces, name)


def load_MED(filename, name=None):
    """Loads MED mesh files generated by SALOME MECA.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    MED files have a 1-indexing
    """

    try:
        import h5py
    except ImportError:
        raise ImportError('MED file format reader needs h5py module to be installed')

    _check_file(filename)

    file = h5py.File(filename)

    list_of_names = []
    file.visit(list_of_names.append)

    # TODO: gerer les cas ou on a que des tris ou que des quads...
    nb_quadrangles = nb_triangles = 0

    for item in list_of_names:
        if '/NOE/COO' in item:
            vertices = file.get(item).value.reshape((3, -1)).T
            nv = vertices.shape[0]
        if '/MAI/TR3/NOD' in item:
            triangles = file.get(item).value.reshape((3, -1)).T - 1
            nb_triangles = triangles.shape[0]
        if '/MAI/QU4/NOD' in item:
            quadrangles = file.get(item).value.reshape((4, -1)).T - 1
            nb_quadrangles = quadrangles.shape[0]

    file.close()

    if nb_triangles == 0:
        triangles = np.zeros((0, 4), dtype=np.int)
    else:
        triangles = np.column_stack((triangles, triangles[:, 0]))
    if nb_quadrangles == 0:
        quadrangles = np.zeros((0, 4), dtype=np.int)

    faces = np.zeros((nb_triangles+nb_quadrangles, 4), dtype=np.int)
    faces[:nb_triangles] = triangles
    # faces[:nb_triangles, -1] = triangles[:, 0]
    faces[nb_triangles:] = quadrangles

    vertices = np.ascontiguousarray(vertices)
    return Mesh(vertices, faces)


def load_WRL(filename, name=None):
    """Loads VRML 2.0 mesh files.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh
    """

    from vtk import vtkVRMLImporter
    import re

    _check_file(filename)

    # Checking version
    with open(filename, 'r') as f:
        line = f.readline()
        ver = re.search(r'#VRML\s+V(\d.\d)', line).group(1)
        if not ver == '2.0':
            raise NotImplementedError('VRML loader only supports VRML 2.0 format (version %s given)' % ver)

    importer = vtkVRMLImporter()
    importer.SetFileName(filename)
    importer.Update()

    actors = importer.GetRenderer().GetActors()
    actors.InitTraversal()
    dataset = actors.GetNextActor().GetMapper().GetInput()

    return _dump_vtk(dataset)


def load_NEM(filename, name=None):
    """Loads mesh files that are used by the ``Mesh`` tool included in Nemoh.

    Parameters
    ----------
    filename: str
        name of the meh file on disk

    Returns
    -------
    Mesh
        the loaded mesh

    Note
    ----
    This format is different from that is used directly by Nemoh software. It is only dedicated to the Mesh tool.
    """

    _check_file(filename)

    ifile = open(filename, 'r')

    nv = int(ifile.readline())
    nf = int(ifile.readline())

    vertices = []
    for ivertex in range(nv):
        vertices.append(list(map(float, ifile.readline().split())))
    vertices = np.asarray(vertices, dtype=np.float)

    faces = []
    for iface in range(nf):
        faces.append(list(map(int, ifile.readline().split())))
    faces = np.asarray(faces, dtype=np.int)
    faces -= 1

    return Mesh(vertices, faces, name)


extension_dict = {  # keyword, reader
    'dat': load_MAR,
    'mar': load_MAR,
    'nemoh': load_MAR,
    'wamit': load_GDF,
    'gdf': load_GDF,
    'diodore-inp': load_INP,
    'inp': load_INP,
    'diodore-dat': load_DAT,
    'hydrostar': load_HST,
    'hst': load_HST,
    'natural': load_NAT,
    'nat': load_NAT,
    'gmsh': load_MSH,
    'msh': load_MSH,
    'rad': load_RAD,
    'radioss': load_RAD,
    'stl': load_STL,
    'vtu': load_VTU,
    'vtp': load_VTP,
    'paraview-legacy': load_VTK,
    'vtk': load_VTK,
    'tecplot': load_TEC,
    'tec': load_TEC,
    'med': load_MED,
    'salome': load_MED,
    'vrml': load_WRL,
    'wrl': load_WRL,
    'nem': load_NEM,
    'nemoh_mesh': load_NEM
}
