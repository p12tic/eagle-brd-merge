#!/usr/bin/env python3
'''
Copyright (C) 2016  Povilas Kanapickas <povilas@radix.lt>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see http://www.gnu.org/licenses/.
'''

''' We operate on the Eagle XML files directly instead of parsing them into
    some kind of intermediate structure. We only care about very limited subset
    of information, thus complete format support is unnecessary.
'''

from copy import deepcopy
import os
import sys
import lxml.etree as etree
from functools import cmp_to_key
import re

class InputFile:

    def __init__(self):
        self.path = None
        self.offsetx = 0
        self.offsety = 0
        self.rotation = 0

def print_usage_and_exit():
    print('''Usage:
    merge.py output-file [in-file [--offx offset-x] [--offy offset-y] [--rotation rotation]]...
    ''')
    sys.exit(1)

def print_file_error_and_exit(infile, el, err = "Unexpected element"):
    print("For file {0}".format(infile.path))
    print("Error : " + el.getroottree().getpath(el) + " : " + err)
    sys.exit(2)

def print_file_warning(infile, warn):
    print("For file {0}".format(infile.path))
    print("Warning : " + warn)

def parse_offset(val):
    if val.endswith('mm'):
        try:
            return float(val[:-2])
        except:
            pass

    print("Can't parse {0} as an offset value. Were units forgotten?".format(val))
    print_usage_and_exit()

def parse_rotation(val):
    if val in ['0', '90', '180', '270']:
        return int(val)
    print("Can't parse {0} as a rotation value. Supported rotations are 0, 90, 180, 270.".format(val))
    print_usage_and_exit()

def fetch_arg(num):
    if num >= len(sys.argv):
        print('Too few arguments specified. Expected at least one more')
        print_usage_and_exit()
    return sys.argv[num]

def parse_args():

    outfile = fetch_arg(1)
    infiles = []
    infile = None

    i = 2
    while i < len(sys.argv):
        arg = fetch_arg(i)
        if arg.startswith('-'):
            # Apply one option to current input file
            if arg == '--offx':
                infile.offsetx = parse_offset(fetch_arg(i+1))
            elif arg == '--offy':
                infile.offsety = parse_offset(fetch_arg(i+1))
            elif arg == '--rotation':
                infile.rotation = parse_rotation(fetch_arg(i+1))
            else:
                print("Unsupported option {0}".format(arg))
                print_usage_and_exit()
            i = i + 2
        else:
            # Start with new input file
            if infile != None:
                infiles.append(infile)
            infile = InputFile()
            infile.path = arg
            i = i + 1

    if infile != None:
        infiles.append(infile)

    return (outfile, infiles)

''' Retrieves a child of lxml element el which matches the given criteria:
     * has matching tag
     * has at least the given attributes with matching values. If None is
        specified, any value is accepted
    If child is not found, None is returned
'''
def find_child(el, tag, attrs = {}):
    for child in el:
        if child.tag == tag:
            valid = True
            for key in attrs:
                attr = child.get(key)
                if attr != attrs[key] and attrs[key] != None:
                    valid = False
            if valid:
                return child
    return None

''' Same as find_child, except that if the child is not fould, a new one with
    the given tag is created.
'''
def find_or_create_child(el, tag, attrs = {}):
    child = find_child(el, tag, attrs)
    if child != None:
        return child
    return etree.SubElement(el, tag)

''' Compares two Xml trees
'''
def xml_tree_compare(a, b):
    # compare root node
    if a.tag < b.tag:
        return -1
    elif a.tag > b.tag:
        return 1
    elif a.tail < b.tail:
        return -1
    elif a.tail > b.tail:
        return 1

    # compare attributes
    aitems = a.attrib.items()
    aitems.sort()
    bitems = b.attrib.items()
    bitems.sort()
    if aitems < bitems:
        return -1
    elif aitems > bitems:
        return 1

    # compare child nodes
    achildren = list(a)
    achildren.sort(key=cmp_to_key(xml_tree_compare))
    bchildren = list(b)
    bchildren.sort(key=cmp_to_key(xml_tree_compare))

    for achild, bchild in zip(achildren, bchildren):
        cmpval = xml_tree_compare(achild, bchild)
        if  cmpval < 0:
            return -1
        elif cmpval > 0:
            return 1

    # must be equal
    return 0

def sync_child_error(el, tag, child, infile, err = None):
    if err == None:
        err = "Unsupported difference"

    el_child = find_child(el, tag)
    if el_child == None:
        el.append(deepcopy(child))
    elif xml_tree_compare(el_child, child) != 0:
        print_file_error_and_exit(infile, child, err + "\n" +
                                    etree.tostring(el_child).decode() + "\n" +
                                    etree.tostring(child).decode())

def sync_child(el, tag, child):
    if find_child(el, tag) == None:
        el.append(deepcopy(child))

# Merges /eagle/drawing/settings element
def merge_xml_settings(out_el, in_el, infile):
    for child in in_el:
        if child.tag == "setting":
            if len(child) > 0:
                print_file_error_and_exit(infile, child, "Expected empty")

            # find any setting matching attributes
            attrs = child.attrib
            attrs = { key : None for key, value in attrs.items() }

            found = find_child(out_el, "setting", attrs)

            if found == None:
                out_el.append(deepcopy(child))
            else:
                # check if elements are equivalent
                if xml_tree_compare(found, child) != 0:
                    print_file_warning(infile, "Incompatible settings \n" +
                                       etree.tostring(found).decode() + "\n" +
                                       etree.tostring(child).decode())
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing/layers element
def merge_xml_layers(out_el, in_el, infile):
    # we only ensure that layer exists, layer info differences are ignored.
    for child in in_el:
        if child.tag == "layer":
            if find_child(out_el, "layer", { "number" : child.get("number") }) == None:
                out_el.append(deepcopy(child))
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

def offset_and_rotate(x, y, infile):
    if infile.rotation == 0:
        pass
    elif infile.rotation == 90:
        tmp = -y
        y = x
        x = tmp
    elif infile.rotation == 180:
        x = -x
        y = -y
    elif infile.rotation == 270:
        tmp = y
        y = -x
        x = tmp
    else:
        assert False

    x += infile.offsetx
    y += infile.offsety
    return x, y

def update_xml_routing_pos(el, xattr, yattr, infile):
    x = el.get(xattr)
    y = el.get(yattr)
    if x == None or y == None:
        print_file_error_and_exit(infile, el)
    x, y = offset_and_rotate(float(x), float(y), infile)
    el.set(xattr, str(x))
    el.set(yattr, str(y))

def update_xml_routing_rot(el, rotattr, infile):
    rot = el.get(rotattr)
    if rot == None or rot == "":
        rot = "R0"
    m = re.match(r"^([a-zA-Z]*)(\d+)$", rot)
    if m == None:
        print_file_error_and_exit(infile, el, "Unsupported rotation attribute " + rot)
    prefix = m.group(1)
    introt = int(m.group(2))

    # rotate mirrored parts to opposite direction
    if "M" in prefix:
        introt = (introt - infile.rotation) % 360
    else:
        introt = (introt + infile.rotation) % 360
    rot = prefix + str(introt)

    if el.get(rotattr) == None and rot == "R0":
        # no changes needed
        return
    el.set(rotattr, rot)

# Updates the elements within the following nodes and all their sub-nodes:
# plain, signal, elements
# This is where the actual position and rotation modifications are made
def update_routing(el, infile):
    if el.tag == "wire":
        # in plain or signal
        update_xml_routing_pos(el, "x1", "y1", infile)
        update_xml_routing_pos(el, "x2", "y2", infile)
    elif el.tag == "polygon":
        # in plain or signal
        for child in el:
            update_routing(child, infile) # process vertex nodes
    elif el.tag == "text":
        # in plain
        update_xml_routing_pos(el, "x", "y", infile)
        update_xml_routing_rot(el, "rot", infile)
    elif el.tag == "dimension":
        # in plain
        update_xml_routing_pos(el, "x1", "y1", infile)
        update_xml_routing_pos(el, "x2", "y2", infile)
        update_xml_routing_pos(el, "x3", "y3", infile)
    elif el.tag == "circle":
        # in plain
        update_xml_routing_pos(el, "x", "y", infile)
    elif el.tag == "rectangle":
        # in plain
        update_xml_routing_pos(el, "x1", "y1", infile)
        update_xml_routing_pos(el, "x2", "y2", infile)
        # note that we are ignoring rotation as it will be dealt with by
        # changing the positions of the corners of the rectangle
    elif el.tag == "frame":
        # in plain
        update_xml_routing_pos(el, "x1", "y1", infile)
        update_xml_routing_pos(el, "x2", "y2", infile)
    elif el.tag == "hole":
        # in plain
        update_xml_routing_pos(el, "x", "y", infile)
    elif el.tag == "contactref":
        # in signal
        pass
    elif el.tag == "via":
        # in signal
        update_xml_routing_pos(el, "x", "y", infile)
    elif el.tag == "element":
        # in elements
        update_xml_routing_pos(el, "x", "y", infile)
        update_xml_routing_rot(el, "rot", infile)
        for child in el:
            update_routing(child, infile) # process attribute or variant nodes
    elif el.tag == "vertex":
        # in polygon
        update_xml_routing_pos(el, "x", "y", infile)
    elif el.tag == "attribute":
        # in element
        update_xml_routing_pos(el, "x", "y", infile)
        update_xml_routing_rot(el, "rot", infile)
    elif el.tag == "variant":
        # in element
        pass
    else:
        print_file_error_and_exit(infile, el)

# Hides the current name label and adds a custom label that is displayed as if
# the element has old_name.
def override_name_label(el, old_name):

    if el.get("name") == old_name:
        return
    name_attr = find_child(el, "attribute", { "name" : "NAME" })
    if name_attr == None:
        return
    name_attr_dup = deepcopy(name_attr)
    name_attr_dup.set("name", "NAME1")
    name_attr_dup.set("value", old_name)
    el.append(name_attr_dup)
    name_attr.set("display", "off")

# Merges /eagle/drawing/board/plain element
def append_xml_plain(out_el, in_el, infile):

    for child in in_el:
        new_child = deepcopy(child)
        out_el.append(new_child)
        update_routing(new_child, infile)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing/board/libraries/library/packages element
def merge_xml_packages(out_el, in_el, infile):

    for child in in_el:
        if child.tag == "package":
            out_child = find_child(out_el, "package", { "name" : child.get("name") })
            if out_child == None:
                out_el.append(deepcopy(child))
            else:
                if xml_tree_compare(out_child, child) != 0:
                    err = "Embedded libraries contain different packages of the same name {0}\n".format(child.get("name"))
                    err += etree.tostring(out_child).decode() + "\n"
                    err += etree.tostring(child).decode()
                    print_file_error_and_exit(infile, child, err)
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing/board/libraries/library element
def merge_xml_library(out_el, in_el, infile):
    assert out_el.get("name") == in_el.get("name")

    for child in in_el:
        if child.tag == "description":
            sync_child(out_el, "description", child)
        elif child.tag == "packages":
            merge_xml_packages(find_or_create_child(out_el, "packages"), child, infile)
        else:
            print_file_error_and_exit(infile, child)

    #if len(in_el.attrib) > 0:
    #    print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing/board/libraries element
def merge_xml_libraries(out_el, in_el, infile):

    for child in in_el:
        if child.tag == "library":
            out_child = find_child(out_el, "library", { "name" : child.get("name") })
            if out_child == None:
                out_el.append(deepcopy(child))
            else:
                merge_xml_library(out_child, child, infile)
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing/board/elements element
# Eagle requires that real names of elements are not duplicated, thus this
# function ensures that a unique name is used. The label is overridden to
# display the old name by defining a custom attribute.
def append_xml_elements(out_el, in_el, element_map, infile):

    for child in in_el:
        if child.tag == "element":
            new_child = deepcopy(child)
            update_routing(new_child, infile)

            # make sure the name of the new signal is unique
            name = new_child.get("name")
            prev_name = name
            postfix = ""
            postfix_num = 1
            while find_child(out_el, "element", { "name" : name + postfix }) != None:
                postfix = "_" + str(postfix_num)
                postfix_num += 1
            name = name + postfix

            new_child.set("name", name)
            if name != prev_name:
                element_map[prev_name] = name
                override_name_label(new_child, prev_name)

            out_el.append(new_child)
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

def update_signal_element_names(el, element_map):
    if el.tag != "contactref":
        return
    name = el.get("element")
    if name != None and name in element_map:
        el.set("element", element_map[name])

# Merges /eagle/drawing/board/signals element
def append_xml_signals(out_el, in_el, element_map, infile):

    for child in in_el:
        if child.tag == "signal":
            new_child = deepcopy(child)
            for new_child2 in new_child:
                update_routing(new_child2, infile)
                update_signal_element_names(new_child2, element_map)

            # make sure the name of the new signal is unique
            name = new_child.get("name")
            postfix = ""
            postfix_num = 1
            while find_child(out_el, "signal", { "name" : name + postfix }) != None:
                postfix = str(postfix_num)
                postfix_num += 1
            name = name + postfix

            new_child.set("name", name)
            out_el.append(new_child)
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing/board/errors element
def append_xml_errors(out_el, in_el, infile):
    # TODO
    pass

# Merges /eagle/drawing/board element
def merge_xml_board(out_el, in_el, infile):

    # Element names must be unique; this dict stores the old->new name mapping
    element_map = {}

    for child in in_el:
        if child.tag == "plain":
            append_xml_plain(find_or_create_child(out_el, "plain"), child, infile)
        elif child.tag == "libraries":
            merge_xml_libraries(find_or_create_child(out_el, "libraries"), child, infile)
        elif child.tag == "attributes":
            sync_child_error(out_el, "attributes", child, infile) # differences not supported
        elif child.tag == "variantdefs":
            sync_child_error(out_el, "variantdefs", child, infile) # differences not supported
        elif child.tag == "classes":
            sync_child_error(out_el, "classes", child, infile) # differences not supported
        elif child.tag == "designrules":
            # ensure that design rule info is equivalent
            sync_child_error(out_el, "designrules", child, infile, "Design rules must be equivalent")
        elif child.tag == "autorouter":
            # we just take the autorouter element of the first file it exists
            sync_child(out_el, "autorouter", child)
        elif child.tag == "elements":
            append_xml_elements(find_or_create_child(out_el, "elements"), child, element_map, infile)
        elif child.tag == "signals":
            append_xml_signals(find_or_create_child(out_el, "signals"), child, element_map, infile)
        elif child.tag == "errors":
            append_xml_errors(find_or_create_child(out_el, "errors"), child, infile)
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle/drawing element
def merge_xml_drawing(out_el, in_el, infile):

    for child in in_el:
        if child.tag == "settings":
            merge_xml_settings(find_or_create_child(out_el, "settings"), child, infile)
        elif child.tag == "grid":
            # we just take the grid element of the first file
            sync_child(out_el, "grid", child)
        elif child.tag == "layers":
            merge_xml_layers(find_or_create_child(out_el, "layers"), child, infile)
        elif child.tag == "board":
            merge_xml_board(find_or_create_child(out_el, "board"), child, infile)
        else:
            print_file_error_and_exit(infile, child)

    if len(in_el.attrib) > 0:
        print_file_error_and_exit(infile, in_el, "Unexpected attributes")

# Merges /eagle element
def merge_xml_eagle(out_el, in_el, infile):
    assert out_el.tag == "eagle" and in_el.tag == "eagle"

    in_attrs = in_el.attrib
    for attr in in_attrs:
        if attr == "version":
            in_version = in_el.get("version")
            out_version = out_el.get("version")
            if out_version == None:
                out_el.set("version", in_version)
            else:
                if in_version != out_version:
                    print_file_error_and_exit(infile, in_el,
                                            "Eagle version mismatch: {0} != {1}".format(in_version, out_version))
        else:
            print_file_error_and_exit(infile, in_el, "Unexpected attributes")


    for child in in_el:
        if child.tag == "drawing":
            merge_xml_drawing(find_or_create_child(out_el, "drawing"), child, infile)
        elif child.tag == "compatibility":
            print_file_warning(infile, "Compatibility notes ignored")

def main():
    outfile, infiles = parse_args()

    out_el = etree.Element("eagle")
    for infile in infiles:
        if not os.path.exists(infile.path):
            print("Input file {0} not found!".format(infile.path))
            sys.exit(1)

        in_el = etree.parse(infile.path)
        merge_xml_eagle(out_el, in_el.getroot(), infile)

    open(outfile, "wb").write(etree.tostring(out_el, xml_declaration=True,
                                            encoding="UTF-8",
                                            doctype="<!DOCTYPE eagle SYSTEM \"eagle.dtd\">"))

if __name__ == "__main__":
    main()
