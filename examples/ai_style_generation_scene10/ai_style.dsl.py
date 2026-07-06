# Add the three angle markers of triangle ABC. These angle objects are not
# present in the imported GeoGebra construction, so this is DSL-level geometry.
tri_angle_A = Angle(C, A, B, name="tri_angle_A")
tri_angle_B = Angle(A, B, C, name="tri_angle_B")
tri_angle_C = Angle(B, C, A, name="tri_angle_C")

style(
    tri_angle_A,
    tri_angle_B,
    tri_angle_C,
    stroke="#e1533f",
    stroke_width_px=1.1,
    stroke_opacity=1,
    fill="#ffe3df",
    fill_opacity=1,
    arc_size_px=14,
    arc_shift_px=1.5,
    auto_radius=True,
    label_visible=False,
    z_index=0.2,
    z_index_fill=0.08,
)
