A = Point(0, 0)
B = Point(4, 0)
C = Point(1, 3)

tri, AB, BC, CA = Polygon(A, B, C)

area_measure = Area(tri)
perimeter_measure = Perimeter(tri)

style(tri, label_visible=True, label_text=f"Area = {area_measure.data.value:.2f}")
style(BC, label_visible=True, label_text=f"Perimeter = {perimeter_measure.data.value:.2f}")

style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
