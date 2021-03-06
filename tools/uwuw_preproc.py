#!/usr/bin/python

# Imports
import os
import string
import argparse

# Dependencies
from itaps import iMesh, iBase
from pyne import material
from pyne.material import Material, MaterialLibrary
from pyne.tally import Tally
from pyne.particle import is_valid, name


# list of fluka predefined materials:
fluka_lib = ["BERYLLIU", "BARIUM", "BISMUTH", "BROMINE", "RHENIUM", "RUTHERFO",
             "ROENTGEN", "HYDROGEN", "PHOSPHO", "GERMANIU", "GADOLINI", "GALLIUM", "HASSIUM",
             "ZINC", "HAFNIUM", "MERCURY", "HELIUM", "PRASEODY", "PLATINUM", "239-PU", "LEAD",
             "CARBON", "POTASSIU", "OXYGEN", "SULFUR", "TUNGSTEN", "EUROPIUM", "MAGNESIU",
             "MOLYBDEN", "MANGANES", "URANIUM", "IRON", "NICKEL", "NITROGEN", "SODIUM", "NIOBIUM",
             "NEODYMIU", "NEON", "ZIRCONIU", "BORON", "COBALT", "FLUORINE", "CALCIUM", "CERIUM",
             "CADMIUM", "VANADIUM", "CESIUM", "CHROMIUM", "COPPER", "STRONTIU", "KRYPTON",
             "SILICON", "TIN", "SAMARIUM", "SCANDIUM", "ANTIMONY", "LANTHANU", "CHLORINE",
             "LITHIUM", "TITANIUM", "TERBIUM", "99-TC", "TANTALUM", "SILVER", "IODINE", "IRIDIUM",
             "241-AM", "ALUMINUM", "ARSENIC", "ARGON", "GOLD", "INDIUM", "YTTRIUM", "XENON",
             "HYDROG-1", "DEUTERIU", "TRITIUM", "HELIUM-3", "HELIUM-4", "LITHIU-6", "LITHIU-7",
             "BORON-10", "BORON-11", "90-SR", "129-I", "124-XE", "126-XE", "128-XE", "130-XE",
             "131-XE", "132-XE", "134-XE", "135-XE", "136-XE", "135-CS", "137-CS", "230-TH",
             "232-TH", "233-U", "234-U", "235-U", "238-U"]


def load_mat_lib(filename):
    """
    function that loads PyNE material library
    filename : string of the name of the material library
    returns PyNE MaterialLibrary instance
    """
    mat_lib = material.MaterialLibrary()
    mat_lib.from_hdf5(
        filename, datapath='/material_library/materials', nucpath='/material_library/nucid')
    return mat_lib


def get_tag_values(filename, output_filename):
    """
    function that gets all tags on dagmc geometry
    ------------------------------
    filename : the dagmc filename
    output_filename : output file name set using -o flag
    return vector of tag_values and writes tallies to ouptut .h5m file
    """
    mesh = iMesh.Mesh()
    mesh.load(filename)
    # get all entities
    ents = mesh.getEntities(iBase.Type.all, iMesh.Topology.triangle)
    # get mesh set
    mesh_sets = mesh.getEntSets()
    # for material list extraction:
    # tag_values = []  # list of tag values
    tag_values = []
    # for tally list extraction:
    tally_values = []
    tally_list = []
    tally_objects_list = []
    tally_type_list = []
    tally_particle_list = []
    found_all_tags = 0
    for s in mesh_sets:
        if (found_all_tags == 1):
            break
        # get all tags
        tags = mesh.getAllTags(s)
        # loop over the tags checking for name
        for t in tags:
            # look for NAME tag
            if (t.name == 'NAME'):
                # the handle is the tag name
                t_handle = mesh.getTagHandle(t.name)
                # get the data for the tag, with taghandle in element i
                tag = t_handle[s]
                group_name = tag_to_string(tag)
                if (group_name not in tag_values):
                    tag_values.append(group_name)
                if 'tally' in group_name:
                    (tally_type, tally_particle, object_ID) = get_tally(
                        mesh, s, group_name)
                    tally_type_list.append(tally_type)
                    tally_particle_list.append(tally_particle)
                    tally_objects_list.append(object_ID)
                # last tag we are done
                if any('impl_complement' in s for s in tag_values):
                    found_all_tags = 1
    # create the final tally list of the form tally_values=[('particle',
    # ('tally_type', ['geom_object:ID']))]
    tally_list = zip(tally_type_list, tally_objects_list)
    tally_values = zip(tally_particle_list, tally_list)
    # write tallies to the output h5m file
    write_tally_h5m(tally_values, output_filename)
    print('The groups found in the h5m file are: ')
    print tag_values
    print '----------'
    print('The tally groups found in the h5m file are: ')
    print tally_values
    print '----------'
    return tag_values


def tag_to_string(tag):
    """
    function to transform tags into strings
    tag : string of the tag to be added to tag_list
    returns tag
    """
    a = []
    # since we have a byte type tag loop over the 32 elements
    for part in tag:
        # if the byte char code is non 0
        if (part != 0):
            # convert to ascii
            a.append(str(unichr(part)))
            # join to end string
            tag = ''.join(a)
    return tag


def get_tally(mesh, s, group_name):
    """
    Function that checks the existence of tally groups
    mesh : entire mesh of the dagmc model
    s : set (group) tagged with tally group name  
    tally_type : type of tally (flux, current, etc.)
    tally_particle : name of particle (Neutron, Photon, etc.)
    object_ID : list of the geometry objects included in the tally; ['type:ID']
    """
    # objects included in the tally
    # get the geometry objects included; ID and type of each
    object_ID = get_entity(mesh, s)
    # split on the basis of '/' to get tally type
    tally_type = type_split(group_name)
    # split on the basis of ':' to get the tally particle
    tally_particle = particle_split(group_name)

    return tally_type, tally_particle, object_ID


def get_entity(mesh, mesh_set):
    """
    Function that gets both the ID and type of entities included in the tally group
    ID_list : list of the form ['type:ID'] of geometry objects included
    returns ID_list
    """
    ID_list = []
    # loop over tags checking for name
    for k in mesh_set.getEntSets(hops=-1):
        tags = mesh.getAllTags(k)
        for t in tags:
            # get the type of geometry objects included; vol, surf, etc.
            if t.name == 'CATEGORY':
                category_h = mesh.getTagHandle(t.name)
                category = category_h[k]
                category = tag_to_string(category)
                continue
            # get the ID of geometry objects included
            if t.name == 'GLOBAL_ID':
                ID_h = mesh.getTagHandle(t.name)
                ID = ID_h[k]
                continue
        object_type_id = category + ':' + str(ID)
        ID_list.append(object_type_id)
    return ID_list


def type_split(tally_group_name):
    """
    Function that splits group name on the basis of '/'
    returns tally type
    """
    try:
        tally_type = tally_group_name.split('/')[1]
    except:
        raise Exception(
            "'/' is missing in %s" % tally_group_name)
    if tally_type == '':
        raise Exception("Tally type is missing in %s" % tally_group_name)
    return tally_type


def particle_split(tally_group_name):
    """
    Function that splits group name on the basis of ':'
    returns tally particle
    """
    try:
        group_name = tally_group_name.split('/')
        tally_particle = group_name[0].split(':')[1]
    except:
        raise Exception(
            "':' is missing in %s" % tally_group_name)
    if (tally_particle == ''):
        raise Exception("Tally particle is missing in %s" % tally_group_name)
    # chack the validity of the particle name
    if (is_valid(tally_particle) == False):
        raise Exception(
            "Particle included in group %s is not a valid particle name!" % tally_group_name)
    return tally_particle


def check_matname(tag_values):
    """
    function to check that material group names exist and creates
    a list of names and densities if provided
    -------------------------------------------------
    tag_values : list of tags from dagmc file
    mat_lib : PyNE material library instance
    returns mat_dens_list, a zipped pair of density and material name
    """
    # loop over tags to check the existence of a 'vacuum' group
    for tag in tag_values:
        if ('vacuum' in tag.lower()):
            tag_values.remove(tag)
    g = 0
    mat_list_matname = []  # list of material names
    mat_list_density = []  # list of density if provided in group names
    # loop over the tags in the file to test the existence of a graveyard
    for tag in tag_values:
        if ('graveyard' in tag.lower()):
            g = 1
            continue
        # look for mat, this id's material in group name
        if (tag[0:3] == 'mat'):
            # split on the basis of "/" being delimiter and
            # split colons from name
            if ('/' in tag):
                splitted_group_name = mat_dens_split(tag)
            # otherwise we have only "mat:"
            elif (':' in tag):
                splitted_group_name = mat_split(tag)
            else:
                raise Exception(
                    "':' is absent' in  %s" % tag)
            mat_list_matname.append(splitted_group_name['material'])
            mat_list_density.append(splitted_group_name['density'])
    if (g == 0):
        raise Exception(
            "Graveyard group is missing! You must include a graveyard")
    mat_dens_list = zip(mat_list_matname, mat_list_density)
    # error conditions, no tags found
    if (len(mat_dens_list) == 0):
        raise Exception(
            "No material group names found, you must include materials")

    return mat_dens_list


def mat_dens_split(tag):
    """
    function that splits group name on the basis of '/'
    group name containing both material name and density
    """
    splitted_group_name = {}
    mat_name = tag.split('/')
    if (':' not in mat_name[0]):
        raise Exception(
            "':' is absent in %s" % tag)
    # list of material name only
    matname = mat_name[0].split(':')
    if (len(matname) > 2):
        raise Exception(
            "Wrong format for group name! %s" % tag)
    if (matname[1] == ''):
        raise Exception(
            "Wrong material name in %s" % tag)
    splitted_group_name['material'] = matname[1]
    if (mat_name[1] == ''):
        raise Exception(
            "Extra \'/\' in %s" % tag)
    if (':' not in mat_name[1]):
        raise Exception(
            "':' is absent after the '/' in %s" % tag)
    matdensity = mat_name[1].split(':')
    try:
        matdensity_test = float(matdensity[1])
    except:
        raise Exception(
            "Density is not a float in %s" % tag)
    splitted_group_name['density'] = matdensity[1]
    return splitted_group_name


def mat_split(tag):
    """
    function that splits group name on the basis of ':'
    group name containing only material name
    """
    splitted_group_name = {}
    matname = tag.split(':')
    if (len(matname) > 2):
        raise Exception(
            "Wrong format for group name! %s" % tag)
    if (matname[1] == ''):
        raise Exception(
            "Wrong material name in %s" % tag)
    splitted_group_name['material'] = matname[1]
    splitted_group_name['density'] = ''
    return splitted_group_name


def check_and_create_materials(material_list, mat_lib):
    """
    function that checks the existence of material names on the material
    library and creates a list of materials with attributes/metadata set
    -------------------------------------------------------------
    material_list : vector of material_name & density pairs
    mat_lib : Material library object
    """
    flukamaterials_list = []
    material_object_list = []
    d = 0
    # loop over materials in geometry
    for g in range(len(material_list)):
        material = material_list[g][0]
        # loop over materials in library
        for key in mat_lib.iterkeys():
            if material == key:
                d = d + 1
                # get material
                new_mat = mat_lib.get(key)[:]
                flukamaterials_list.append(material)
                copy_metadata(new_mat, mat_lib.get(key))
                # set the mcnp material number and fluka material name
                set_metadata(new_mat, d, flukamaterials_list)

                # rename the material to match the group
                group_name = "mat:" + material_list[g][0]
                if (material_list[g][1] is not ''):
                    group_name += "/rho:" + material_list[g][1]

                new_mat.metadata['name'] = group_name

                if (material_list[g][1] != ''):
                    new_mat.density = float(material_list[g][1])

                material_object_list.append(new_mat)
                break
            if (mat_lib.keys().index(key) == len(mat_lib.keys()) - 1):
                raise Exception(
                    'Couldn\'t find exact match in material library for : %s' % material)
                print_near_match(material, mat_lib)
    # check that there are as many materials as there are groups
    if d != len(material_list):
        raise Exception("There are insuficient materials")

    # return the list of material objects to write to file
    # print material_object_list
    return material_object_list


def copy_metadata(material, material_from_lib):
    """
    function to copy metadata of materials from the material library
    -------------------------------------
    material : PyNE material object to copy data into 
    material_from_lib : material objec to copy data from
    """
    # copy metadata from lib to material
    for key in list(material_from_lib.metadata.keys()):
        material.metadata[key] = material_from_lib.metadata[key]

    material.density = material_from_lib.density
    material.mass = material_from_lib.mass
    material.atoms_per_molecule = material_from_lib.atoms_per_molecule
    material.comp = material_from_lib.comp
    return material


def set_metadata(mat, number, flukamat_list):
    """
    function to set the metadata of materials:
    ----------------------------------------
    mat : PyNE Material Object
    number : mcnp material number
    flukamat_list : list of materials  
    returns : PyNE Material Object
    """
    mat.metadata['mat_number'] = str(number)
    # The first 25 indices are reserved for fluka
    # built in materials, so we need to start
    # indexing after 25
    mat.metadata['fluka_material_index'] = str(number + 25)
    fluka_material_naming(mat, flukamat_list)
    return mat


def fluka_material_naming(material, flukamat_list):
    """
    Function to prepare fluka material names:
    flukamat_list : list of material names found in group tags on the model 
    """
    matf = material.metadata['name']
    matf = ''.join(c for c in matf if c.isalnum())
    L = len(matf)
    if len(matf) > 8:
        matf = matf[0:8]
    else:
        pass
    # if name is in list, change name by appending number
    if (matf.upper() in flukamat_list) or (matf.upper() in fluka_lib):
        for a in range(len(flukamat_list) + 1):
            a = a + 1
            if (a <= 9):
                if (len(matf) == 8):
                    matf = matf.rstrip(matf[-1])
                    matf = matf + str(a)
                elif (len(matf) < 8):
                    matf = matf[0:L]
                    matf = matf + str(a)
            elif (a > 9):
                if (len(matf) == 8):
                    for i in range(len(str(a))):
                        matf = matf.rstrip(matf[-1])
                    matf = matf + str(a)
                elif (len(matf) < 8) and (8 - len(matf) >= len(str(a))):
                    matf = matf[0:L]
                    matf = matf + str(a)
                elif (len(matf) < 8) and (8 - len(matf) < len(str(a))):
                    difference = len(str(a)) - (8 - len(matf))
                    for i in range(difference):
                        matf = matf.rstrip(matf[-1])
                    matf = matf + str(a)
            if (matf.upper() in flukamat_list) or (matf.upper() in fluka_lib):
                continue
            else:
                flukamat_list.append(matf.upper())
                break
    # otherwise uppercase
    else:
        flukamat_list.append(matf.upper())
    material.metadata['fluka_name'] = matf.upper()
    return material


def print_near_match(material, material_library):
    """ 
    function to print near matches to material name
    material_library : PyNE material library
    """
    list_of_matches = []
    for item in material_library.iterkeys():
        if (material.lower() in item.lower()) or (material.upper() in item.upper()):
            print("Near matches to %s are :" % material)
            print item
        list_of_matches.append(item)
    return list_of_matches


def write_mats_h5m(materials_list, filename):
    """
    Function that writes material objects to output .h5m file
    -------
    material_list: list of materials found on tags of the model
    filename: filename to write the objects to
    """
    new_matlib = MaterialLibrary()
    for material in materials_list:
        # using fluka name as index since this is unique
        new_matlib[material.metadata['fluka_name']] = material
    new_matlib.write_hdf5(filename, datapath='/materials', nucpath='/nucid')


def write_tally_h5m(tally_list, filename):
    """
    Function that writes tally objects to ouptut .h5m file
    -------
    tally_list: list of volume id tally pairs of PyNE Material Objects
    filename: filename to write the objects to
    """
    # tally list contains elements of the form ('photon', ('current', ['Surface:4', 'Volume:1']))
    # loop over list
    for tally in tally_list:
        particle_name = tally[0].capitalize()
        tally_type = tally[1][0]
        for k in range(len(tally[1][1])):
            tally_object = tally[1][1][k].split(':')[0]
            object_id = tally[1][1][k].split(':')[1]
            tally_name = particle_name[
                0:2].upper() + tally_type[0: 7 - len(object_id)] + str(object_id)
            new_tally = Tally(tally_type, particle_name,
                              int(object_id), tally_object, str(object_id), tally_name, 0.0, 1.0)
            new_tally.write_hdf5(filename, "/tally")


def parsing():
    """
    function to parse the script, adding options:
    defining 
    the .h5m file path
    -d  : material library path (nuc_data.h5 if using PyNE)
    -o  : name of the output h5m file "NAME.h5m", if not set the input .h5m file will be used
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
         action='store', dest='datafile', help='The path to the input .h5m file')
    parser.add_argument('-d', action='store', dest='nuc_data',
                        help='The path to the materials library, nuc_data.h5 if using PyNE')
    parser.add_argument(
        '-o', action='store', dest='output', help='The name of the output file NAME.h5m')
    args = parser.parse_args()
    if not args.datafile:
        raise Exception('input h5m file is not provided!!')
    if not args.nuc_data:
        raise Exception('nuc_data file path not specified!!. [-d] is not set')
    if not args.output:
        args.output = args.datafile
    return args


def main():
    """
    main
    """
    # parse script
    args = parsing()
    # first add atomic mass to file
    launch_script = "nuc_data_make -m atomic_mass -o " + args.output
    print launch_script
    os.system(launch_script)
    # load material library
    mat_lib = load_mat_lib(args.nuc_data)
    # get list of tag values
    tag_values = get_tag_values(args.datafile, args.output)
    # check that material tags exist in library # material_list is list of
    # pyne objects in problem
    mat_dens_list = check_matname(tag_values)
    # create material objects from library
    material_object_list = check_and_create_materials(mat_dens_list, mat_lib)
    # write materials to file
    write_mats_h5m(material_object_list, args.output)

if __name__ == "__main__":
    main()
