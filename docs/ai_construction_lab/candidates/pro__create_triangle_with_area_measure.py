A = Point(0, 0)
B = Point(4, 0)
C = Point(1, 3)

triangle, AB, BC, CA = Polygon(A, B, C)

style(A, B, C, label_visible=True)
style(triangle, stroke="color.main", stroke_width_px="line_width.main", fill="color.aux", fill_opacity=0.15)

area_measure = Area(triangle)
perimeter_measure = Perimeter(triangle)

area_val = area_measure.data.value
perimeter_val = perimeter_measure.data.value

style(triangle, label_visible=True, label_text=f"S={area_val:.2f}", label_mode="label_value")

style(AB, label_visible=True, label_text=f"P={perimeter_val:.2f}", label_mode="label_value")
