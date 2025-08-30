
precision highp float;

#define PI 3.14159265358979323846264338327950288
#define SSAO_SAMPLE_NUM 9

in vec2 fragTexCoord;

uniform sampler2D GBufferNormal;
uniform sampler2D GBufferDepth;
uniform mat4 CameraView;
uniform mat4 CameraProjection;
uniform mat4 CameraInvProjection;
uniform mat4 CameraInvViewProjection;
uniform mat4 LightViewProjection;
uniform sampler2D ShadowMap;
uniform vec2 ShadowInvResolution;
uniform float CameraClipNear;
uniform float CameraClipFar;
uniform float LightClipNear;
uniform float LightClipFar;
uniform vec3 LightDirection;

float LinearDepth(float Depth, float Near, float Far)
{
    return (2.0 * Near) / (Far + Near - Depth * (Far - Near));
}

float NonLinearDepth(float Depth, float Near, float Far)
{
    return (((2.0 * Near) / Depth) - Far - Near) / (Near - Far);
}

vec3 CameraSpace(vec2 TexCoord, float Depth)
{
    vec4 PositionClip = vec4(vec3(TexCoord, NonLinearDepth(Depth, CameraClipNear, CameraClipFar)) * 2.0 - 1.0, 1.0);
    vec4 Position = CameraInvProjection * PositionClip;
    return Position.xyz / Position.w;
}

vec3 Rand(vec2 Seed)
{
    return 2.0 * fract(sin(dot(Seed, vec2(12.9898, 78.233))) * vec3(43758.5453, 21383.21227, 20431.20563)) - 1.0;
}

vec2 Spiral(int SampleIndex, float Turns, float Seed)
{
	float Alpha = (float(SampleIndex) + 0.5) / float(SSAO_SAMPLE_NUM);
	float Angle = Alpha * (Turns * 2.0 * PI) + 2.0 * PI * Seed;
	return Alpha * vec2(cos(Angle), sin(Angle));
}

out vec4 finalColor;

void main()
{
    float Depth = texture(GBufferDepth, fragTexCoord).r;
    if (Depth == 1.0f) { discard; }

    // compute shadows
    vec3 PositionClip = vec3(fragTexCoord, NonLinearDepth(Depth, CameraClipNear, CameraClipFar)) * 2.0f - 1.0f;
    vec4 FragPositionHomo = CameraInvViewProjection * vec4(PositionClip, 1.0);
    vec3 FragPosition = FragPositionHomo.xyz / FragPositionHomo.w;
    vec3 FragNormal = texture(GBufferNormal, fragTexCoord).xyz * 2.0 - 1.0;

    vec3 Seed = Rand(fragTexCoord);

    float ShadowNormalBias = 0.01;

    vec4 FragPositionLightSpace = LightViewProjection * vec4(FragPosition + ShadowNormalBias * FragNormal.xyz, 1.0);
    FragPositionLightSpace.xyz /= FragPositionLightSpace.w;
    FragPositionLightSpace.xyz = (FragPositionLightSpace.xyz + 1.0f) / 2.0f;

    float ShadowDepthBias = 0.000005;
    float ShadowClip = float(
        FragPositionLightSpace.x < 1.0 &&
        FragPositionLightSpace.x > 0.0 &&
        FragPositionLightSpace.y < 1.0 &&
        FragPositionLightSpace.y > 0.0);

    float Shadow = 1.0 - ShadowClip * float(
        LinearDepth(FragPositionLightSpace.z, LightClipNear, LightClipFar) - ShadowDepthBias > texture(ShadowMap, FragPositionLightSpace.xy + ShadowInvResolution * Seed.xy).r
    );

    // compute SSAO:
    float Bias = 0.025f;
    float Radius = 0.5f;
    float Turns = 7.0f;
    float Intensity = 0.15f;

    vec3 Normal = mat3(CameraView) * FragNormal;
    vec3 Base = CameraSpace(fragTexCoord, texture(GBufferDepth, fragTexCoord).r);
    float Occlusion = 0.0;
    for (int Index = 0; Index < SSAO_SAMPLE_NUM; ++Index)
    {
        vec3 Next = Base + Radius * vec3(Spiral(Index, Turns, Seed.z), 0.0);
        vec4 NextTex = CameraProjection * vec4(Next, 1.0);
        vec2 SampleTexCoord = (NextTex.xy / NextTex.w) * 0.5 + 0.5;
        vec3 SamplePosition = CameraSpace(SampleTexCoord, texture(GBufferDepth, SampleTexCoord).r);
        vec3 DiffDirection = SamplePosition - Base;

        float VV = dot(DiffDirection, DiffDirection);
        float VN = dot(DiffDirection, Normal) - Bias;
        float F = max(Radius * Radius - VV, 0.0);
        Occlusion += F * F * F * max(VN / (0.001 + VV), 0.0);
    }
    Occlusion = Occlusion / pow(Radius, 6.0);

    float SSAO = max(0.0, 1.0 - Occlusion * Intensity * (5.0 / float(SSAO_SAMPLE_NUM)));
    finalColor.r = SSAO;
    finalColor.g = Shadow;
    finalColor.b = 0.0f;
    finalColor.a = 1.0f;
}