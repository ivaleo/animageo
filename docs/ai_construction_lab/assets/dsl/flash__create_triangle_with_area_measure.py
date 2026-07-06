A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
tri, AB, BC, CA = Polygon(A, B, C)
style(A, B, C, label_visible=True)
area_val = Area(tri)
perim_val = Perimeter(tri)
area_label = f"S = {area_val.data.value:.2f}"
perim_label = f"P = {perim_val.data.value:.2f}"
style(tri, label_text=area_label)
style(AB, label_text=perim_label)
