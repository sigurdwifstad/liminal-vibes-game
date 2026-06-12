from __future__ import annotations

from ursina import Shader


found_footage_shader = Shader(
    name="found_footage_shader",
    language=Shader.GLSL,
    fragment="""
#version 430

uniform sampler2D tex;
uniform float i_time;
uniform float motion_amount;
uniform float intensity;
uniform float aberration_strength;

in vec2 uv;
out vec4 color;

float rand(vec2 p)
{
    return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453123);
}

void main()
{
    vec2 center = vec2(0.5);
    vec2 dir = uv - center;
    float radial = length(dir);

    // -------------------------------------------------
    // VHS-style horizontal jitter
    // -------------------------------------------------
    float lineNoise =
        (rand(vec2(floor(uv.y * 300.0), floor(i_time * 20.0))) - 0.5);

    float horizontalWarp =
        lineNoise * (0.002 + motion_amount * 0.008);

    vec2 warpedUV = uv + vec2(horizontalWarp, 0.0);

    // -------------------------------------------------
    // Chromatic aberration (radial, not directional)
    // -------------------------------------------------
    vec2 aberrDir = normalize(dir + vec2(0.0001));

    float aberrAmount =
        aberration_strength *
        radial *
        (0.0005 + motion_amount * 0.002);

    vec2 redUV =
        clamp(warpedUV + aberrDir * aberrAmount,
              vec2(0.001),
              vec2(0.999));

    vec2 blueUV =
        clamp(warpedUV - aberrDir * aberrAmount,
              vec2(0.001),
              vec2(0.999));

    vec2 greenUV =
        clamp(warpedUV,
              vec2(0.001),
              vec2(0.999));

    vec3 base;
    base.r = texture(tex, redUV).r;
    base.g = texture(tex, greenUV).g;
    base.b = texture(tex, blueUV).b;

    // Blend with original so color splitting is subtle
    vec3 original =
        texture(tex, clamp(warpedUV,
                           vec2(0.001),
                           vec2(0.999))).rgb;

    base = mix(original, base, 0.18);

    // -------------------------------------------------
    // Film grain (monochrome)
    // -------------------------------------------------
    float grain =
        (rand(uv * 2000.0 + i_time * 73.0) - 0.5) *
        (0.05 + motion_amount * 0.15);

    base += grain * intensity;

    // -------------------------------------------------
    // Scanlines (multiplicative)
    // -------------------------------------------------
    float scanline =
        1.0 - (0.03 * intensity) *
        (0.5 + 0.5 * sin(uv.y * 900.0));

    base *= scanline;

    // -------------------------------------------------
    // Tape tracking bands
    // -------------------------------------------------
    float bandPos =
        fract(i_time * 0.12);

    float band =
        smoothstep(0.08, 0.0,
            abs(uv.y - bandPos));

    base += band * 0.06 * intensity;

    // -------------------------------------------------
    // Mild exposure flicker
    // -------------------------------------------------
    float flicker =
        1.0 +
        sin(i_time * 14.0) * 0.008 * intensity;

    base *= flicker;

    // -------------------------------------------------
    // Vignette
    // -------------------------------------------------
    float vignette =
        1.0 -
        smoothstep(0.55, 0.95, radial) * 0.28;

    base *= vignette;

    color = vec4(clamp(base, 0.0, 1.0), 1.0);
}
""",
    geometry="",
    default_input={
        "i_time": 0.0,
        "motion_amount": 0.0,
        "intensity": 1.0,
        "aberration_strength": 0.3
    },
)


