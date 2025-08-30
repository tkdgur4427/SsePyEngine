
precision highp float;

// raylib predefined shader variables:
// - https://github.com/raysan5/raylib/wiki/raylib-default-shader
in vec3 fragPosition;
in vec2 fragTexCoord;
in vec4 fragColor;
in vec3 fragNormal;
uniform vec4 colDiffuse;

// user-defined variables
uniform float Specularity;
uniform float Glossiness;
uniform float CameraClipNear;
uniform float CameraClipFar;

layout (location = 0) out vec4 GBufferColor;
layout (location = 1) out vec4 GBufferNormal;

float Grid(in vec2 Uv, in float LineWidth)
{
    vec4 UvDdxy = vec4(dFdx(Uv), dFdy(Uv));
    vec2 UvDeriv = vec2(length(UvDdxy.xz), length(UvDdxy.yw));
    float TargetWidth = LineWidth > 0.5 ? (1.0 - LineWidth) : LineWidth;
    vec2 DrawWidth = clamp(vec2(TargetWidth, TargetWidth), UvDeriv, vec2(0.5, 0.5));
    vec2 LineAA = UvDeriv * 1.5;
    vec2 GridUv = abs(fract(Uv) * 2.0 - 1.0);
    GridUv = LineWidth > 0.5 ? GridUv : (1.0 - GridUv);
    vec2 G2 = smoothstep(DrawWidth + LineAA, DrawWidth - LineAA, GridUv);
    G2 *= clamp(TargetWidth / DrawWidth, 0.0, 1.0);
    G2 = mix(G2, vec2(TargetWidth, TargetWidth), clamp(UvDeriv * 2.0 - 1.0, 0.0, 1.0));
    G2 = LineWidth > 0.5 ? (1.0 - G2) : G2;
    return mix(G2.x, 1.0, G2.y);
}

float Checker(in vec2 Uv)
{
    vec4 UvDdxy = vec4(dFdx(Uv), dFdy(Uv));
    vec2 W = vec2(length(UvDdxy.xz), length(UvDdxy.yw));
    vec2 I = 2.0 * (abs(fract((Uv - 0.5 * W) * 0.5) - 0.5) - abs(fract((Uv + 0.5 * W) * 0.5) - 0.5)) / W;
    return 0.5 - 0.5 * I.x * I.y;
}

vec3 FromGamma(in vec3 Color)
{
    return vec3(pow(Color.x, 1.0 / 2.2), pow(Color.y, 1.0 / 2.2), pow(Color.z, 1.0 / 2.2));
}

float LinearDepth(float Depth, float Near, float Far)
{
    return (2.0 * Near) / (Far + Near - Depth * (Far - Near));
}

void main()
{
    float GridFine = Grid(20.0 * 10.0 * fragTexCoord, 0.025);
    float GridCoarse = Grid(2.0 * 10.0 * fragTexCoord, 0.02);
    float Check = Checker(2.0 * 10.0 * fragTexCoord);

    vec3 Albedo = FromGamma(fragColor.xyz * colDiffuse.xyz) * mix(mix(mix(0.9, 0.95, Check), 0.85, GridFine), 1.0, GridCoarse);
    float Specular = Specularity * mix(mix(0.5, 0.75, Check), 1.0, GridCoarse);

    GBufferColor = vec4(Albedo, Specular);
    GBufferNormal = vec4(fragNormal * 0.5f + 0.5f, Glossiness / 100.0f);
    gl_FragDepth = LinearDepth(gl_FragCoord.z, CameraClipNear, CameraClipFar);
}
