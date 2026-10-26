from __future__ import annotations

import random

from panda3d.core import PNMImage, Texture as PandaTexture
from ursina import Entity, Texture, Vec3, color


def _build_fabric_texture() -> Texture:
    size = 64
    image = PNMImage(size, size)
    rng = random.Random("liminal_furniture_fabric")
    for y in range(size):
        for x in range(size):
            grain = rng.uniform(-0.04, 0.04)
            stripe = 0.035 if (x // 8 + y // 5) % 7 == 0 else 0.0
            shade = max(-0.09, min(0.08, grain + stripe))
            image.setXel(
                x,
                y,
                max(0.0, min(1.0, 0.32 + shade)),
                max(0.0, min(1.0, 0.14 + shade * 0.62)),
                max(0.0, min(1.0, 0.055 + shade * 0.35)),
            )

    panda_texture = PandaTexture("brown_furniture_fabric")
    panda_texture.load(image)
    texture = Texture(panda_texture)
    texture.filtering = "bilinear"
    return texture


_FABRIC_TEXTURE = None


def get_fabric_texture() -> Texture:
    global _FABRIC_TEXTURE
    if _FABRIC_TEXTURE is None:
        _FABRIC_TEXTURE = _build_fabric_texture()
    return _FABRIC_TEXTURE


def create_furniture(
    kind: str,
    position: Vec3,
    rotation_y: float,
    elevation: float = 0.0,
    on_side: bool = False,
) -> tuple[Entity, float, float]:
    """Build a textured chair or sofa and return its horizontal collision half-extents."""
    global _FABRIC_TEXTURE
    if _FABRIC_TEXTURE is None:
        _FABRIC_TEXTURE = _build_fabric_texture()

    if kind == "sofa":
        width, depth = 1.9, 1.05
        seat_height = 0.52
        back_height = 0.85
    else:
        width, depth = 1.15, 1.0
        seat_height = 0.52
        back_height = 0.8

    rotated = round(rotation_y / 90.0) % 2 == 1
    half_x, half_z = (depth / 2, width / 2) if rotated else (width / 2, depth / 2)
    root = Entity(
        position=Vec3(position.x, position.y + elevation, position.z),
        rotation_y=rotation_y,
    )
    # Lying on its side: local +y maps to +x, so shift to keep the footprint centered
    # and lift so the lowest side rests on the floor.
    body = Entity(parent=root)
    if on_side:
        body.rotation_z = 90
        body.position = Vec3(-0.65, width / 2, 0)
        half_x, half_z = (depth / 2, 0.65) if rotated else (0.65, depth / 2)
    Entity(
        parent=body,
        model="cube",
        position=Vec3(0, 0.58, 0),
        scale=Vec3(width, 1.16, depth),
        color=color.rgba(0, 0, 0, 0),
        collider="box",
    )

    seat = Entity(
        parent=body,
        model="cube",
        position=Vec3(0, seat_height, 0),
        scale=Vec3(width * 0.88, 0.38, depth * 0.86),
        color=color.white,
        texture=_FABRIC_TEXTURE,
        texture_scale=(2, 1.5),
    )
    Entity(
        parent=body,
        model="cube",
        position=Vec3(0, seat_height + back_height * 0.45, -depth * 0.38),
        scale=Vec3(width * 0.9, back_height, depth * 0.18),
        color=color.white,
        texture=_FABRIC_TEXTURE,
        texture_scale=(2, 1.5),
    )

    leg_color = color.rgb(74, 43, 26)
    leg_width = 0.12
    for x_sign in (-1, 1):
        for z_sign in (-1, 1):
            Entity(
                parent=body,
                model="cube",
                position=Vec3(x_sign * width * 0.36, 0.22, z_sign * depth * 0.34),
                scale=Vec3(leg_width, 0.44, leg_width),
                color=leg_color,
            )

    if kind == "sofa":
        for x_sign in (-1, 1):
            Entity(
                parent=body,
                model="cube",
                position=Vec3(x_sign * width * 0.43, seat_height + 0.1, 0),
                scale=Vec3(width * 0.16, 0.48, depth * 0.9),
                color=color.white,
                texture=_FABRIC_TEXTURE,
                texture_scale=(1, 1.5),
            )
    else:
        Entity(
            parent=body,
            model="cube",
            position=Vec3(0, seat_height + back_height * 0.44, -depth * 0.35),
            scale=Vec3(width * 0.85, back_height * 0.92, depth * 0.15),
            color=color.white,
            texture=_FABRIC_TEXTURE,
        )

    return root, half_x, half_z
