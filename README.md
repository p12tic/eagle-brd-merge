
Overview
--------

This command-line tool merges several board files produced by CadSoft Eagle CAD
software into one, effectively reimplementing the panelize.ulp script included
in the program itself, but without the board size limit in the light and
freeware editions of the program.

The tool helps to perform panelization of one or several designs into a board
larger than the board size limit. The output is a regular Eagle board file
which can be easily inspected. Moreover, it's possible to perform various
additional modifications, as Eagle only restricts component movement outside
the board size limits. This is especially useful in cases when the production
facility requires all panelized boards to be connected somehow, which is
the case with most low-cost prototype PCB producers.

Operation
---------

The tool copies the board data optionally rotating the board and adding a
position offset to the coordinates. The included component data is correctly
merged.

If several input files use the same component from the same library, the
duplicates are removed. The user must ensure that the input files use up-to
date libraries. If there is a mismatch between the definitions of the same
component used in different files, the program aborts.

The tool may change signal or element names to ensure that resulting output file
does not have signals or elements with duplicate names. This is required by
Eagle. Whenever element name is changed, the tool ensures that the displayed
label stays the same by introducing a custom attribute which is displayed
instead of the name attribute.

All input files should use the same design rules. If there is a mismatch, the
program aborts.

This tool does not support board files produced by Eagle versions earlier than
6.0. Most features of the newer board files are supported. The program aborts
whenever unsupported feature is encountered.

Usage
-----

    merge.py output-file [in-file [--offx offset-x] [--offy offset-y] [--rotation rotation]]...

 - `output-file`: path to the output .brd file
 - `in-file`: path to an input .brd file
 - `offset-x`, `offset-y`: the position offset to apply to the particular input file.
   The suffix determines the units. The following suffixes are supported:
     - mm: millimeters
 - `rotation`: The counter-clockwise rotation in degrees to apply to the
   particular input file. The following values are supported: `0`, `90`, `180`
   and `270`.

Requirements
------------

python3 and lxml are required.

License
-------

The tool is licensed under General Public License.

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






