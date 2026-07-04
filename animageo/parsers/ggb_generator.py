import os
import shutil
from xml.etree import ElementTree
from xml.etree.ElementTree import Element as XElement  # shortened "XML Element"

from ..geo.construction import Construction
from ..geo.lib_commands import Command
from ..geo.lib_elements import *
from ..geo.lib_vars import *

from ..parsers import ggb_parser

temp_path = os.path.join(os.getcwd(), "/temp")
#source_path = os.path.join(os.getcwd(), "GeoGebra/project", "source")

#--------------------------------------------------------------------------

def convert_zip(folder_path: str, archive_path: str = None):
    if not archive_path:
        archive_path = folder_path
    try:
        os.remove(f"{folder_path}.zip")
    except FileNotFoundError:
        pass
    shutil.make_archive(archive_path, "zip", folder_path)

#--------------------------------------------------------------------------

def get_comm_xelem(comm: Command): # -> XElement:
    comm_xelem = XElement(
        "command",
        attrib={
            "name": comm.name
        }
    )
    comm_xelem.extend(
        [
            XElement(
                "input",
                attrib={f"a{ind}": input for ind, input in enumerate(comm.inputs)}
            ),
            XElement(
                "output",
                attrib={f"a{ind}": output for ind, output in enumerate(comm.outputs)}
            )
        ]
    )

    return comm_xelem

def line_coords(data): #: Line | Ray | Segment) -> tuple[int, int, int]:  # line equation coefficients
    return *data.n, -data.c

def conic_matrix(data): #: Circle | Arc) -> tuple[int, int, int, int, int, int]:
    return 1, 1, data.c[0]**2 + data.c[1]**2 - data.r_squared, 0, -data.c[0], -data.c[1]

def get_points_xelems(comm: Command, constr: Construction): #) -> tuple[XElement]:
    elem_xelems = []
    for output in comm.outputs:  # Intersection command can output more than one element
        point_elem = constr.element(output)
        
        elem_xelem = XElement(
            "element",
            attrib={
                "type": point_elem.data.__class__.__name__.lower(),
                "label": point_elem.name
            }
        )
        elem_xelem.extend(
            [
                XElement(
                    "show",
                    attrib={
                        "object": str(point_elem.visible).lower(),
                        "label": "true"
                    }
                ),
                XElement(
                    "objColor",
                    attrib={name: str(value) for name, value in zip(("r", "g", "b", "alpha"), (97, 97, 97, 0) if comm.name in ("Intersect", "Midpoint") else (21, 101, 192, 0))}
                ),
                XElement(
                    "layer",
                    attrib={
                        "val": "0"
                    }
                ),
                XElement(
                    "labelMode",
                    attrib={
                        "val": "0"
                    }
                ),
                XElement(
                    "animation",
                    attrib={
                        "step": "0.1",
                        "speed": "1",
                        "type": "1",
                        "playing": "false"
                    }
                ),
                XElement(
                    "auxiliary",
                    attrib={
                        "val": "false"
                    }
                ),
                XElement(
                    "coords",
                    attrib={
                        "x": str(point_elem.data.coords[0]),
                        "y": str(point_elem.data.coords[1]),
                        "z": "1"
                    }
                ),
                XElement(
                    "pointSize",
                    attrib={
                        "val": "4" if comm.name in ("Intersect", "Midpoint") else "5"
                    }
                ),
                XElement(
                    "pointStyle",
                    attrib={
                        "val": "0"
                    }
                )
            ]
        )
        
        elem_xelems.append(elem_xelem)
    
    if comm.name == "Point" and len(comm.inputs) == 2:
        if filter(lambda input: input.isalnum(), comm.inputs):
            exp_xelem = XElement(
                "expression",
                attrib={
                    "label": point_elem.name,
                    "exp": f"({', '.join(comm.inputs)})",
                    "type": "point"
                }
            )
            elem_xelems.insert(0, exp_xelem)
        
        return tuple(elem_xelems)
    
    return get_comm_xelem(comm), *elem_xelems

def get_lines_xelems(comm: Command, constr: Construction): #) -> tuple[XElement]:
    elem_xelems = []
    for output in comm.outputs:  # AngularBisector and Tangent command can output two elements
        line_elem = constr.element(output)
        coords = line_coords(line_elem.data)
        
        elem_xelem = XElement(
            "element",
            attrib={
                "type": line_elem.data.__class__.__name__.lower(),
                "label": line_elem.name
            }
        )
        elem_xelem.extend(
            [
                XElement(
                    "show",
                    attrib={
                        "object": str(line_elem.visible).lower(),
                        "label": "false"
                    }
                ),
                XElement(
                    "objColor",
                    attrib={name: str(value) for name, value in zip(("r", "g", "b", "alpha"), (97, 97, 97, 0))}
                ),
                XElement(
                    "layer",
                    attrib={
                        "val": "0"
                    }
                ),
                XElement(
                    "labelMode",
                    attrib={
                        "val": "0"
                    }
                ),
                XElement(
                    "coords",
                    attrib={name: str(value) for name, value in zip("xyz", coords)}
                ),
                XElement(
                    "lineStyle",
                    attrib={
                        "thickness": "5",
                        "type": "0",
                        "typeHidden": "1",
                        "opacity": "204"
                    }
                ),
                XElement(
                    "eqnStyle",
                    attrib={
                        "style": "explicit"
                    }
                )
            ]
        )
        if comm.name in ("Ray", "Segment"):
            elem_xelem.extend(
            [
                XElement(
                    "outlyingIntersections",
                    attrib={
                        "val": "false"
                    }
                ),
                XElement(
                    "keepTypeOnTransform",
                    attrib={
                        "val": "true"
                    }
                )
            ]
        )

        elem_xelems.append(elem_xelem)
    
    return get_comm_xelem(comm), *elem_xelems

def get_conics_xelems(comm: Command, constr: Construction): #) -> tuple[XElement]:
    conic_elem = constr.element(comm.outputs[0])
    matrix = conic_matrix(conic_elem.data)

    elem_xelem = XElement(
        "element",
        attrib={
            "type": conic_elem.name,
            "label": comm.outputs[0]
        }
    )
    elem_xelem.extend(
        [
            XElement(
                "show",
                attrib={
                    "object": str(conic_elem.visible).lower(),
                    "label": "false"
                }
            ),
            XElement(
                "objColor",
                attrib={name: str(value) for name, value in zip(("r", "g", "b", "alpha"), (97, 97, 97, 0))}
            ),
            XElement(
                "layer",
                attrib={
                    "val": "0"
                }
            ),
            XElement(
                "labelMode",
                attrib={
                    "val": "0"
                }
            ),
            XElement(
                "lineStyle",
                attrib={
                    "thickness": "5",
                    "type": "0",
                    "typeHidden": "1",
                    "opacity": "204"
                }
            ),
            XElement(
                "eigenvectors",
                attrib={name: str(value) for name, value in zip(("x0", "y0", "z0", "x1", "y1", "z1"), (1, 0, 1.0, 0, 1, 1.0))}
            ),
            XElement(
                "matrix",
                attrib={f"A{ind}": str(value) for ind, value, in enumerate(matrix)}
            ),
            XElement(
                "eqnStyle",
                attrib={
                    "style": "specific"
                }
            )
        ]
    )
    if comm.name == "Semicircle":
        elem_xelem.extend(
            [
                XElement(
                    "outlyingIntersections",
                    attrib={
                        "val": "false"
                    }
                ),
                XElement(
                    "keepTypeOnTransform",
                    attrib={
                        "val": "true"
                    }
                )
            ]
        )
    
    return get_comm_xelem(comm), elem_xelem

def get_vars_xelem(var: Var): # -> XElement:
    if type(var.data) != AngleSize:
        limit = 10 ** len(str(int(var.data) + 1).replace("-", ""))
    
    elem_xelem = XElement(
        "element",
        attrib={
            "type": "angle" if type(var.data) == AngleSize else "numeric",
            "label": var.name
        }
    )
    elem_xelem.extend(
        [
            XElement(
                "value",
                attrib={
                    "val": str(var.data.value) if type(var.data) == AngleSize else str(var.data)
                }
            ),
            XElement(
                "slider",
                attrib={
                    "min": "0°" if type(var.data) == AngleSize else str(-limit),
                    "max": "360°" if type(var.data) == AngleSize else str(limit),
                    "absoluteScreenLocation": "true",
                    "width": "200",
                    "x": "100",
                    "y": "100",
                    "fixed": "false",
                    "horizontal": "true",
                    "showAlgebra": "true"
                }
            ),
            XElement(
                "show",
                attrib={
                    "object": "true",
                    "label": "true"
                }
            ),
            XElement(
                "objColor",
                attrib={name: str(value) for name, value in zip(("r", "g", "b", "alpha"), (0, 0, 0, 0.1))}
            ),
            XElement(
                "layer",
                attrib={
                    "val": "0"
                }
            ),
            XElement(
                "labelMode",
                attrib={
                    "val": "1"
                }
            ),
            XElement(
                "lineStyle",
                attrib={
                    "thickness": "10",
                    "type": "0",
                    "typeHidden": "1",
                    "opacity": "153" if type(var.data) == AngleSize else "255"
                }
            ),
            XElement(
                "animation",
                attrib={
                    "speed": "1",
                    "type": "0",
                    "playing": "false"
                }
            )
        ]
    )
    if type(var.data) == AngleSize:
        elem_xelem.extend(
            [
                XElement(
                    "angleStyle",
                    attrib={
                        "val": "3"
                    }
                ),
                XElement(
                    "arcSize",
                    attrib={
                        "val": "30"
                    }
                )
            ]
        )
    
    return elem_xelem

#--------------------------------------------------------------------------

def save(constr: Construction, path: str): # -> None:
    #shutil.copytree(source_path, temp_path)
    
    xml = ElementTree.parse(os.path.join(temp_path, "geogebra.xml"))
    constr_xelem = xml.find("construction")
    
    for var in constr.vars:
        if type(var.data) == Measure:
            continue
        xelem = get_vars_xelem(var)
        constr_xelem.append(xelem)
    
    for comm in constr.commands:
        if comm.name in ("Point", "Intersect", "Midpoint", "Rotate", "Translate"):
            xelems = get_points_xelems(comm, constr)
        elif comm.name in ("Line", "OrthogonalLine", "LineBisector", "AngularBisector", "Tangent", "Ray", "Segment"):
            xelems = get_lines_xelems(comm, constr)
        elif comm.name in ("Circle", "Semicircle"):
            xelems = get_conics_xelems(comm, constr)
        
        constr_xelem.extend(xelems)

    xml.write(os.path.join(temp_path, "geogebra.xml"), encoding="utf-8")
    
    convert_zip(temp_path, path)

    if os.access(path, os.F_OK):
        os.remove(path)
    os.rename(f"{path}.zip", path)
    
    shutil.rmtree(temp_path)

#--------------------------------------------------------------------------

if __name__ == "__main__":
    constr = ggb_parser.load(os.path.join("files", "all_elements.ggb"))
    save(constr, os.path.join("files", "temp.ggb"))
